import pygame
import math
import time
import random
import os
import multiprocessing as mp
from enum import Enum
from typing import Tuple

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
    DANCING = "dancing"  # Nuova espressione

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

        # State & Animation
        self._expression = Expression.NEUTRAL
        self._auto_blink = auto_blink
        self._speaking = False
        self._blink_val = 0.0
        self._blink_timer = 0.0
        self._next_blink = random.uniform(2.5, 5.5)
        self._speak_phase = 0.0
        self._spd = 5.0

        # Animazioni Speciali
        self._nod_timer = 0.0
        self._nod_active = False
        self._eye_offset_x = 0.0 # Nuovo offset per ballo
        self._eye_offset_y = 0.0
        self._loading_angle = 0.0 
        
        # Parametri Ballo
        self.dance_rhythm = 6.0   # Velocità del ritmo
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

    def _set_defaults(self):
        # Riferimento basato sulla dimensione minore per la scala generale
        r = min(self.width, self.height)
        self._ref = r
        is_portrait = self.height > self.width

        # 1. Definiamo le dimensioni degli occhi
        eye_w = 0.22 * r
        eye_h = 0.45 * r  
        
        # 2. SPOSTAMENTO VERSO L'ALTO
        # Ridotto da 0.45 a 0.30 (più basso è il valore, più in alto va il viso)
        eye_y = 0.30 * self.height 

        # 3. Calcoliamo la posizione della bocca
        # Rimane ancorata al bordo inferiore degli occhi, quindi salirà insieme a loro
        mouth_y_aligned = eye_y + (eye_h / 3) + (0.05 * r)

        self._t = {
            "eye_w": eye_w,
            "eye_h": eye_h,
            "eye_y": eye_y,
            "eye_rot_l": 0.0,
            "eye_rot_r": 0.0,
            "eye_radius": 0.15 * r,
            "eye_spacing": 0.30 * self.width,
            "mouth_w": 0.30 * r if is_portrait else 0.20 * r,
            "mouth_h": 0.05 * r,
            "mouth_y": mouth_y_aligned, 
            "mouth_curve": 0.3,
            "mouth_open": 1.0,
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
        
        # Gestione Movimento Occhi (Ballo + Nod)
        target_off_x = 0.0
        target_off_y = 0.0

        if self._expression == Expression.DANCING:
            self._dance_timer += dt
            # Movimento a "otto"
            target_off_x = math.sin(self._dance_timer * self.dance_rhythm) * (self._ref * 0.15)
            target_off_y = math.cos(self._dance_timer * self.dance_rhythm * 2) * (self._ref * 0.08)
        else:
            self._dance_timer = 0.0

        if self._nod_active:
            self._nod_timer += dt
            nod_speed, nod_amplitude = 12.0, self._ref * 0.08
            target_off_y += math.sin(self._nod_timer * nod_speed) * nod_amplitude
            if self._nod_timer > 1.2:
                self._nod_active = False

        self._eye_offset_x = target_off_x
        self._eye_offset_y = target_off_y
        
        block_blink = [Expression.SLEEPING, Expression.IN_LOVE, Expression.LOADING, Expression.HAPPY]
        if self._auto_blink and self._expression not in block_blink:
            self._blink_timer += dt
            if self._blink_timer >= self._next_blink:
                self._blink_val = 1.0
                self._blink_timer = 0.0
                self._next_blink = random.uniform(2.5, 5.0)
            self._blink_val = max(0, self._blink_val - dt * 10.0)
        else:
            self._blink_val = 0

        if self._speaking: self._speak_phase += dt * 12.0

    def _draw(self):
        self.screen.fill(self.bg_color)
        # Applica offset X e Y agli occhi
        cx = (self.width // 2) + int(self._eye_offset_x)
        cy = int(self._eye_y + self._eye_offset_y)
        
        for side in [-1, 1]:
            self._draw_eye(cx + side * int(self._eye_spacing), cy, side)
        
        # La bocca segue parzialmente il movimento verticale
        self._draw_mouth(int(self._mouth_y + self._eye_offset_y * 0.5))

    def _draw_eye(self, cx, cy, side):
        pulse = 1.0
        color = self.eye_color
        
        if self._expression == Expression.IN_LOVE:
            pulse = 1.0 + 0.15 * math.sin(time.time() * 12)
            color = (255, 40, 100)
        
        w = int(self._eye_w * pulse)
        h = int(self._eye_h * (1.0 - self._blink_val) * pulse)
        if h < 2: h = 2
        
        surf = pygame.Surface((w * 2, h * 2), pygame.SRCALPHA)
        rect = pygame.Rect(w // 2, h // 2, w, h)
        
        if self._expression == Expression.LOADING:
            start_angle = math.radians(self._loading_angle if side > 0 else -self._loading_angle)
            end_angle = start_angle + math.pi
            pygame.draw.arc(surf, color, rect, start_angle, end_angle, 8)
            
        elif self._expression == Expression.HAPPY:
            thickness = max(10, int(self._ref * 0.03))
            pygame.draw.arc(surf, color, rect, 0, math.pi, thickness)
            
        elif self._expression == Expression.IN_LOVE:
            self._draw_heart(surf, color, rect)
        else:
            pygame.draw.rect(surf, color, rect, border_radius=int(self._eye_radius))
            rot = self._eye_rot_l if side < 0 else self._eye_rot_r
            if abs(rot) > 0.1: 
                surf = pygame.transform.rotate(surf, rot)
            
        self.screen.blit(surf, surf.get_rect(center=(cx, cy)))

    def _draw_heart(self, surface, color, rect):
        x, y, w, h = rect
        if self.heart_original:
            scaled_heart = pygame.transform.smoothscale(self.heart_original, (w, h))
            surface.blit(scaled_heart, (x, y))
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
        self._listener_thread = None

    def _target(self, conn, kwargs):
        face = RobotFace(**kwargs)
        running = True
        while running:
            dt = face.clock.tick(face.fps) / 1000.0
            while conn.poll():
                cmd, val = conn.recv()
                if cmd == "EXPR": face.set_expression(val)
                elif cmd == "SPEAK": face._speaking = val
                elif cmd == "NOD": face.start_nod()
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
            
            # Avviamo il thread di ascolto per i messaggi di ritorno (es. click)
            import threading
            from event_manager import EventManager
            def listen():
                em = EventManager()
                while self._process and self._process.is_alive():
                    try:
                        if self._parent_conn.poll(0.1):
                            cmd, val = self._parent_conn.recv()
                            if cmd == "CLICK":
                                em.publish("joystick", {"action": "click"})
                    except EOFError:
                        break
                    except Exception:
                        break
            
            self._listener_thread = threading.Thread(target=listen, daemon=True)
            self._listener_thread.start()

    def stop(self):
        if self._process and self._process.is_alive():
            self._parent_conn.send(("STOP", None))
            self._process.join()

    def set_expression(self, expr: Expression):
        self._parent_conn.send(("EXPR", expr))

    def set_speaking(self, status: bool):
        self._parent_conn.send(("SPEAK", status))

    def nod(self):
        self._parent_conn.send(("NOD", None))

# ====================================================================
# MAIN DI TEST
# ====================================================================

if __name__ == "__main__":
    manager = RobotFaceManager(fullscreen=False)
    manager.start()

    print("--- Test Robot Face ---")
    
    try:
        expressions = list(Expression)
        idx = 0
        
        while True:
            current_expr = expressions[idx]
            print(f"Espressione corrente: {current_expr.name}")
            manager.set_expression(current_expr)
            
            # Se sta ballando, facciamolo parlare un po'
            if current_expr == Expression.DANCING:
                manager.set_speaking(True)
                time.sleep(4)
                manager.set_speaking(False)
            elif current_expr in [Expression.HAPPY, Expression.ANGRY]:
                manager.nod()
                manager.set_speaking(True)
                time.sleep(2)
                manager.set_speaking(False)
            else:
                time.sleep(2)
            
            idx = (idx + 1) % len(expressions)
            
    except KeyboardInterrupt:
        print("\nChiusura...")
    finally:
        manager.stop()