import pygame
import math
import time
import random
import os
import multiprocessing as mp
from enum import Enum
from typing import Tuple
import threading
from event_manager import EventManager

# ====================================================================
# DEFINIZIONI E LOGICA CORE (RobotFace)
# ====================================================================

class Expression(Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    THOUGHTFUL = "thoughtful"
    IN_LOVE = "in_love"
    SLEEPING = "sleeping"
    LOADING = "loading"
    DANCING = "dancing"
    DOWNLOADING = "downloading"

class RobotFace:
    def __init__(self, bg_color=(20, 20, 30), eye_color=(0, 210, 255), 
                 mouth_color=(0, 210, 255), fps=60, auto_blink=True, fullscreen=False):
        pygame.init()
        info = pygame.display.Info()
        if fullscreen:
            self.width, self.height = info.current_w, info.current_h
            flags = pygame.FULLSCREEN
        else:
            self.width, self.height = 480, 800
            flags = 0

        self.screen = pygame.display.set_mode((self.width, self.height), flags)
        pygame.mouse.set_visible(False)
        
        self.bg_color = bg_color
        self.eye_color = eye_color
        self.mouth_color = mouth_color
        self.fps = fps
        self.clock = pygame.time.Clock()
        self._ref = min(self.width, self.height)

        # Asset Cuore
        self.heart_path = os.path.join("display", "assets", "heart.svg")
        self.heart_original = None
        if os.path.exists(self.heart_path):
            try:
                self.heart_original = pygame.image.load(self.heart_path).convert_alpha()
            except: pass

        # Font per il testo
        self._font = pygame.font.SysFont("Arial", int(self._ref * 0.06), bold=True)
        self._current_text = ""
        self._wrapped_lines = [] 

        # State & Animation
        self._expression = Expression.NEUTRAL
        self._auto_blink = auto_blink
        self._speaking = False
        self._blink_val = 0.0
        self._blink_timer = 0.0
        self._next_blink = random.uniform(2.5, 5.5)
        self._speak_phase = 0.0
        self._spd = 5.0

        # Livello Wi-Fi iniziale (da 0.0 a 1.0)
        self._wifi_pct = 1.0 

        # Animazioni Speciali
        self._nod_timer = 0.0
        self._nod_active = False
        self._eye_offset_x = 0.0
        self._eye_offset_y = 0.0
        self._loading_angle = 0.0 
        self._download_progress = 0.0
        self.dance_rhythm = 6.0
        self._dance_timer = 0.0

        # Parametri correnti e target
        self._eye_w = self._eye_h = self._eye_rot_l = self._eye_rot_r = 0.0
        self._eye_spacing = 0.40 * self._ref
        self._eye_y = self._eye_radius = 0.0
        self._mouth_w = self._mouth_h = self._mouth_y = self._mouth_curve = self._mouth_open = 0.0
        
        self._t = {}
        self._set_defaults()
        self._update_targets()
        self._sync_instantly()

    def _wrap_text(self, text, max_width):
        words = text.split(' ')
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            w, _ = self._font.size(test_line)
            
            if w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
                    current_line = []
        
        if current_line:
            lines.append(' '.join(current_line))
        return lines

    def set_text(self, text):
        self._current_text = text if text else ""
        if not self._current_text:
            self._wrapped_lines = []
            return

        max_w_px = self.width * 0.8
        raw_lines = self._current_text.split('\n')
        self._wrapped_lines = []
        for rl in raw_lines:
            self._wrapped_lines.extend(self._wrap_text(rl, max_w_px))

    def set_wifi_level(self, percentage: float):
        """Imposta il livello del segnale wifi (0.0 a 1.0 o 0 a 100)."""
        if percentage > 1.0:
            percentage /= 100.0
        self._wifi_pct = max(0.0, min(1.0, percentage))

    def _set_defaults(self):
        r = min(self.width, self.height)
        self._ref = r
        is_portrait = self.height > self.width
        eye_w, eye_h = 0.22 * r, 0.42 * r  
        eye_y = 0.25 * self.height 
        mouth_y_aligned = eye_y + (eye_h / 2.5) + (0.05 * r)

        self._t = {
            "eye_w": eye_w, "eye_h": eye_h, "eye_y": eye_y,
            "eye_rot_l": 0.0, "eye_rot_r": 0.0, "eye_radius": 0.15 * r,
            "eye_spacing": 0.30 * self.width,
            "mouth_w": 0.30 * r if is_portrait else 0.20 * r,
            "mouth_h": 0.05 * r, "mouth_y": mouth_y_aligned, 
            "mouth_curve": 0.3, "mouth_open": 1.0,
        }

    def _update_targets(self):
        self._set_defaults()
        r, e = self._ref, self._expression
        if e == Expression.HAPPY:
            self._t["eye_h"], self._t["mouth_curve"], self._t["mouth_h"] = 0.25*r, 1.0, 0.12*r
            self._t["eye_w"] = 0.32 * r
        elif e == Expression.SAD:
            self._t["eye_rot_l"], self._t["eye_rot_r"], self._t["mouth_curve"] = 15.0, -15.0, -0.8
        elif e == Expression.ANGRY:
            self._t["eye_h"], self._t["eye_rot_l"], self._t["eye_rot_r"] = 0.18*r, -18.0, 18.0
            self._t["mouth_curve"], self._t["mouth_w"] = -0.5, 0.18*r
        elif e == Expression.THOUGHTFUL:
            self._t["eye_h"], self._t["eye_w"] = 0.05 * r, 0.35 * r
            self._t["mouth_w"], self._t["mouth_h"], self._t["mouth_curve"] = 0.10 * r, 0.01 * r, 0.0
        elif e == Expression.IN_LOVE:
            self._t["eye_w"], self._t["eye_h"] = 0.35*r, 0.35*r
            self._t["mouth_curve"], self._t["mouth_h"] = 1.2, 0.12*r
        elif e == Expression.LOADING:
            self._t["eye_w"], self._t["eye_h"] = 0.25*r, 0.25*r
            self._t["mouth_w"], self._t["mouth_h"], self._t["mouth_curve"] = 0.1*r, 0.01*r, 0.0
        elif e == Expression.SLEEPING:
            self._t["eye_h"], self._t["mouth_h"], self._t["mouth_open"] = 0.018*r, 0.012*r, 0.3
        elif e == Expression.DANCING:
            self._t["eye_w"], self._t["eye_h"] = 0.28*r, 0.38*r
            self._t["mouth_curve"], self._t["mouth_w"] = 0.6, 0.26*r
        elif e == Expression.DOWNLOADING:
            self._t["eye_w"], self._t["eye_h"] = 0.25*r, 0.35*r
            self._t["mouth_w"], self._t["mouth_h"], self._t["mouth_curve"] = 0.15*r, 0.01*r, 0.0

    def _sync_instantly(self):
        for k, v in self._t.items(): setattr(self, f"_{k}", v)

    def set_expression(self, expression):
        if expression != self._expression:
            self._expression = expression
            self._update_targets()

    def start_nod(self):
        self._nod_active = True
        self._nod_timer = 0.0

    def _update(self, dt):
        for k, v in self._t.items():
            curr = getattr(self, f"_{k}")
            setattr(self, f"_{k}", curr + (v - curr) * (1.0 - math.exp(-self._spd * dt)))
        
        if self._expression == Expression.LOADING:
            self._loading_angle += dt * 360

        if self._expression == Expression.DOWNLOADING:
            self._download_progress += dt * 0.25
            if self._download_progress > 1.0:
                self._download_progress = 0.0

        target_off_x = target_off_y = 0.0
        if self._expression == Expression.DANCING:
            self._dance_timer += dt
            target_off_x = math.sin(self._dance_timer * self.dance_rhythm) * (self._ref * 0.12)
            target_off_y = math.cos(self._dance_timer * self.dance_rhythm * 2) * (self._ref * 0.06)

        if self._nod_active:
            self._nod_timer += dt
            target_off_y += math.sin(self._nod_timer * 12.0) * (self._ref * 0.08)
            if self._nod_timer > 1.2: self._nod_active = False

        self._eye_offset_x, self._eye_offset_y = target_off_x, target_off_y
        
        block_blink = [Expression.SLEEPING, Expression.IN_LOVE, Expression.LOADING, Expression.HAPPY, Expression.DOWNLOADING]
        if self._auto_blink and self._expression not in block_blink:
            self._blink_timer += dt
            if self._blink_timer >= self._next_blink:
                self._blink_val = 1.0
                self._blink_timer = 0.0
                self._next_blink = random.uniform(2.5, 5.0)
            self._blink_val = max(0, self._blink_val - dt * 10.0)
        else: self._blink_val = 0

        if self._speaking: self._speak_phase += dt * 12.0

    def _draw_wifi(self):
        """Disegna l'indicatore wifi a 6 barre in alto a destra."""
        num_bars = 6
        # Parametri proporzionali allo schermo
        margin_right = int(self.width * 0.05)
        margin_top = int(self.height * 0.03)
        bar_w = max(4, int(self._ref * 0.015))
        bar_gap = max(2, int(self._ref * 0.008))
        max_bar_h = int(self._ref * 0.06)
        
        # Punto iniziale (destra verso sinistra)
        start_x = self.width - margin_right - (num_bars * (bar_w + bar_gap))
        
        # Colore spento (sfondo oscurato)
        bg_bar_color = (int(self.eye_color[0]*0.15), int(self.eye_color[1]*0.15), int(self.eye_color[2]*0.15))

        # Determina quante barrette accendere in base alla percentuale
        active_bars = round(self._wifi_pct * num_bars)

        for i in range(num_bars):
            # Le barre crescono linearmente in altezza
            bar_h = int((i + 1) * (max_bar_h / num_bars))
            x = start_x + i * (bar_w + bar_gap)
            y = margin_top + (max_bar_h - bar_h)
            
            color = self.eye_color if i < active_bars else bg_bar_color
            pygame.draw.rect(self.screen, color, (x, y, bar_w, bar_h), border_radius=int(bar_w // 2))

    def _draw(self):
        self.screen.fill(self.bg_color)
        
        # Indicatore Wi-Fi
        self._draw_wifi()
        
        # 1. Disegno Volto
        cx = (self.width // 2) + int(self._eye_offset_x)
        cy = int(self._eye_y + self._eye_offset_y)
        for side in [-1, 1]:
            self._draw_eye(cx + side * int(self._eye_spacing), cy, side)
        self._draw_mouth(int(self._mouth_y + self._eye_offset_y * 0.5))

        # 2. Disegno Testo Wrappato
        if self._wrapped_lines:
            line_height = self._font.get_linesize()
            total_text_h = len(self._wrapped_lines) * line_height
            start_y = int(self.height * 0.85) - (total_text_h // 2)
            
            for i, line in enumerate(self._wrapped_lines):
                txt_surf = self._font.render(line, True, self.eye_color)
                y_pos = start_y + (i * line_height)
                txt_rect = txt_surf.get_rect(center=(self.width // 2, y_pos))
                self.screen.blit(txt_surf, txt_rect)

    def _draw_eye(self, cx, cy, side):
        pulse = 1.0
        color = self.eye_color
        if self._expression == Expression.IN_LOVE:
            pulse = 1.0 + 0.15 * math.sin(time.time() * 12)
            color = (255, 40, 100)
        
        w, h = int(self._eye_w * pulse), int(self._eye_h * (1.0 - self._blink_val) * pulse)
        if h < 2: h = 2
        
        surf = pygame.Surface((w * 2, h * 2), pygame.SRCALPHA)
        rect = pygame.Rect(w // 2, h // 2, w, h)
        
        if self._expression in [Expression.HAPPY, Expression.LOADING]:
            arc_surf = pygame.Surface((w * 2, h * 2))
            arc_surf.set_colorkey((0, 0, 0))
            if self._expression == Expression.LOADING:
                start = math.radians(self._loading_angle if side > 0 else -self._loading_angle)
                pygame.draw.arc(arc_surf, color, rect, start, start + math.pi, 8)
            else: 
                thick = max(10, int(self._ref * 0.035))
                pygame.draw.arc(arc_surf, color, rect, 0, math.pi, thick)
            surf.blit(arc_surf, (0, 0))
        elif self._expression == Expression.IN_LOVE:
            self._draw_heart(surf, color, rect)
            
        elif self._expression == Expression.DOWNLOADING: 
            bg_eye_color = (int(color[0]*0.2), int(color[1]*0.2), int(color[2]*0.2))
            fill_color = (min(255, int(color[0] * 1.3 + 50)), min(255, int(color[1] * 1.3 + 50)), min(255, int(color[2] * 1.3 + 50)))
            
            pygame.draw.rect(surf, bg_eye_color, rect, border_radius=int(self._eye_radius))
            
            progress_surf = pygame.Surface((w * 2, h * 2), pygame.SRCALPHA)
            pygame.draw.rect(progress_surf, fill_color, rect, border_radius=int(self._eye_radius))
            
            fill_h = int(h * self._download_progress)
            clip_rect = pygame.Rect(w // 2, (h // 2) + h - fill_h, w, fill_h)
            
            surf.blit(progress_surf, clip_rect, clip_rect)
            
        else:
            pygame.draw.rect(surf, color, rect, border_radius=int(self._eye_radius))
            rot = self._eye_rot_l if side < 0 else self._eye_rot_r
            if abs(rot) > 0.1: surf = pygame.transform.rotate(surf, rot)
            
        self.screen.blit(surf, surf.get_rect(center=(cx, cy)))

    def _draw_heart(self, surface, color, rect):
        x, y, w, h = rect
        if self.heart_original:
            scaled = pygame.transform.smoothscale(self.heart_original, (w, h))
            surface.blit(scaled, (x, y))
        else:
            pts = [(x, y + h * 0.35), (x + w // 2, y + h), (x + w, y + h * 0.35)]
            pygame.draw.polygon(surface, color, pts)
            r = w // 4
            pygame.draw.circle(surface, color, (x + r, y + r), r)
            pygame.draw.circle(surface, color, (x + w - r, y + r), r)

    def _draw_mouth(self, mouth_y):
        cx, cy, w, h = self.width//2, mouth_y, int(self._mouth_w), int(self._mouth_h)
        if self._speaking: h = int(h * (0.3 + 0.7 * abs(math.sin(self._speak_phase))))
        if h < 3:
            pygame.draw.line(self.screen, self.mouth_color, (cx-w//2, cy), (cx+w//2, cy), 4)
            return
        pts = []
        n = 30
        if self._mouth_curve >= 0:
            pts.extend([(cx-w//2, cy), (cx+w//2, cy)])
            for i in range(n+1):
                a = math.pi * i / n
                pts.append((cx + int(w/2 * math.cos(a)), cy + int(h * self._mouth_curve * math.sin(a))))
        else:
            for i in range(n+1):
                a = math.pi + math.pi * i / n
                pts.append((cx + int(w/2 * math.cos(a)), cy + int(h * abs(self._mouth_curve) * math.sin(a))))
            pts.extend([(cx+w//2, cy), (cx-w//2, cy)])
        if len(pts) > 2: pygame.draw.polygon(self.screen, self.mouth_color, pts)

# ====================================================================
# GESTORE DEL PROCESSO
# ====================================================================

class RobotFaceManager:
    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._parent_conn, self._child_conn = mp.Pipe()
        self._process = None
        self._expression = Expression.NEUTRAL

    def get_expression(self):
        return self._expression

    def _target(self, conn, kwargs):
        face = RobotFace(**kwargs)
        running = True
        while running:
            dt = face.clock.tick(face.fps) / 1000.0
            while conn.poll():
                cmd, val = conn.recv()
                if cmd == "EXPR": 
                    face.set_expression(val)
                    self._expression = val
                elif cmd == "SPEAK": face._speaking = val
                elif cmd == "NOD": face.start_nod()
                elif cmd == "TEXT": face.set_text(val)
                elif cmd == "WIFI": face.set_wifi_level(val)  # <--- GESTIONE COMANDO WIFI
                elif cmd == "STOP": running = False
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: running = False
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE: running = False
                if ev.type == pygame.MOUSEBUTTONDOWN or ev.type == pygame.FINGERDOWN:
                    conn.send(("CLICK", None))
            face._update(dt)
            face._draw()
            pygame.display.flip()
        pygame.quit()

    def start(self):
        if not self._process or not self._process.is_alive():
            self._process = mp.Process(target=self._target, args=(self._child_conn, self._kwargs))
            self._process.daemon = True
            self._process.start()
            
            def listen():
                em = EventManager()
                while self._process and self._process.is_alive():
                    try:
                        if self._parent_conn.poll(0.1):
                            cmd, val = self._parent_conn.recv()
                            if cmd == "CLICK": em.publish("joystick", {"action": "click"})
                    except: break
            threading.Thread(target=listen, daemon=True).start()

    def stop(self):
        if self._process and self._process.is_alive():
            self._parent_conn.send(("STOP", None))
            self._process.join()

    def set_expression(self, expr: Expression): self._parent_conn.send(("EXPR", expr))
    def set_speaking(self, status: bool): self._parent_conn.send(("SPEAK", status))
    def set_text(self, text: str): self._parent_conn.send(("TEXT", text))
    def set_wifi_level(self, percentage: float): self._parent_conn.send(("WIFI", percentage)) # <--- NUOVO METODO MANAGER
    def nod(self): self._parent_conn.send(("NOD", None))

if __name__ == "__main__":
    manager = RobotFaceManager(fullscreen=False)
    manager.start()
    try:
        manager.set_expression(Expression.HAPPY)
        manager.set_text("Segnale Ottimo!")
        manager.set_wifi_level(1.0) # 100% (Accende tutte e 6 le barre)
        time.sleep(3)
        
        manager.set_expression(Expression.THOUGHTFUL)
        manager.set_text("Segnale scarso...")
        manager.set_wifi_level(0.30) # 30% (Accende circa 2 barre su 6)
        time.sleep(3)
        
        manager.set_text("Nessun Segnale")
        manager.set_wifi_level(0.0) # 0% (Tutto spento/scuro)
        time.sleep(2)
    except KeyboardInterrupt: pass
    finally: manager.stop()