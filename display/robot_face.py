import pygame
import math
import time
import random
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

class RobotFace:
    """Renders the face. To be used inside a dedicated process."""
    def __init__(self, bg_color=(20, 20, 30), eye_color=(0, 210, 255), 
                 mouth_color=(0, 210, 255), fps=60, auto_blink=True, fullscreen=True):
        pygame.init()
        info = pygame.display.Info()
        if fullscreen:
            self.width, self.height = info.current_w, info.current_h
            flags = pygame.FULLSCREEN
        else:
            self.width, self.height = 800, 480
            flags = 0

        self.screen = pygame.display.set_mode((self.width, self.height), flags)
        pygame.mouse.set_visible(False)
        
        self.bg_color = bg_color
        self.eye_color = eye_color
        self.mouth_color = mouth_color
        self.fps = fps
        self.clock = pygame.time.Clock()
        self._ref = min(self.width, self.height)

        # State & Animation
        self._expression = Expression.NEUTRAL
        self._auto_blink = auto_blink
        self._speaking = False
        self._blink_val = 0.0
        self._blink_timer = 0.0
        self._next_blink = random.uniform(2.5, 5.5)
        self._speak_phase = 0.0
        self._spd = 5.0

        # Parametri correnti e target
        self._eye_w = self._eye_h = self._eye_rot_l = self._eye_rot_r = 0.0
        self._eye_spacing = 0.30 * self._ref
        self._eye_y = self._eye_radius = 0.0
        self._mouth_w = self._mouth_h = self._mouth_y = self._mouth_curve = self._mouth_open = 0.0
        
        self._t = {}
        self._set_defaults()
        self._update_targets()
        self._sync_instantly() # Evita animazione di "nascita" all'avvio

    def _set_defaults(self):
        r = self._ref
        self._t = {
            "eye_w": 0.15 * r, "eye_h": 0.22 * r, "eye_y": 0.38 * self.height,
            "eye_rot_l": 0.0, "eye_rot_r": 0.0, "eye_radius": 0.04 * r,
            "mouth_w": 0.22 * r, "mouth_h": 0.07 * r, "mouth_y": 0.66 * self.height,
            "mouth_curve": 0.3, "mouth_open": 1.0,
        }

    def _update_targets(self):
        self._set_defaults()
        r, e = self._ref, self._expression
        if e == Expression.HAPPY:
            self._t["eye_h"], self._t["mouth_curve"], self._t["mouth_h"] = 0.15*r, 1.0, 0.10*r
        elif e == Expression.SAD:
            self._t["eye_rot_l"], self._t["eye_rot_r"], self._t["mouth_curve"] = 15.0, -15.0, -0.8
        elif e == Expression.ANGRY:
            self._t["eye_h"], self._t["eye_rot_l"], self._t["eye_rot_r"] = 0.13*r, -18.0, 18.0
            self._t["mouth_curve"], self._t["mouth_w"] = -0.5, 0.18*r
        elif e == Expression.SLEEPING:
            self._t["eye_h"], self._t["mouth_h"], self._t["mouth_open"] = 0.018*r, 0.012*r, 0.3

    def _sync_instantly(self):
        for k, v in self._t.items(): setattr(self, f"_{k}", v)

    def set_expression(self, expression):
        if expression != self._expression:
            self._expression = expression
            self._update_targets()

    def _update(self, dt):
        # Smoothing
        for k, v in self._t.items():
            curr = getattr(self, f"_{k}")
            setattr(self, f"_{k}", curr + (v - curr) * (1.0 - math.exp(-self._spd * dt)))
        
        # Blink logic
        if self._auto_blink and self._expression != Expression.SLEEPING:
            self._blink_timer += dt
            if self._blink_timer >= self._next_blink:
                self._blink_val = 1.0 # Blink istantaneo semplificato o gestisci ciclo
                self._blink_timer = 0.0
                self._next_blink = random.uniform(2.5, 5.0)
            self._blink_val = max(0, self._blink_val - dt * 10.0)

        if self._speaking: self._speak_phase += dt * 12.0

    def _draw(self):
        self.screen.fill(self.bg_color)
        cx, cy = self.width // 2, int(self._eye_y)
        for side in [-1, 1]:
            self._draw_eye(cx + side * int(self._eye_spacing), cy, self._eye_rot_l if side < 0 else self._eye_rot_r)
        self._draw_mouth()

    def _draw_eye(self, cx, cy, rot):
        w, h = int(self._eye_w), int(self._eye_h * (1.0 - self._blink_val))
        if h < 2: h = 2
        surf = pygame.Surface((w*2, h*2), pygame.SRCALPHA)
        rect = pygame.Rect(w//2, h//2, w, h)
        pygame.draw.rect(surf, self.eye_color, rect, border_radius=int(self._eye_radius))
        if abs(rot) > 0.1: surf = pygame.transform.rotate(surf, rot)
        self.screen.blit(surf, surf.get_rect(center=(cx, cy)))

    def _draw_mouth(self):
        cx, cy, w, h = self.width//2, int(self._mouth_y), int(self._mouth_w), int(self._mouth_h)
        if self._speaking: h = int(h * (0.3 + 0.7 * abs(math.sin(self._speak_phase))))
        if h < 3:
            pygame.draw.line(self.screen, self.mouth_color, (cx-w//2, cy), (cx+w//2, cy), 3)
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
# GESTORE DEL PROCESSO (RobotFaceManager)
# ====================================================================

class RobotFaceManager:
    """Interfaccia per controllare il robot da un altro processo."""
    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._parent_conn, self._child_conn = mp.Pipe()
        self._process = None

    def _target(self, conn, kwargs):
        """Loop eseguito nel processo secondario."""
        face = RobotFace(**kwargs)
        running = True
        while running:
            dt = face.clock.tick(face.fps) / 1000.0
            
            # Gestione Comandi
            while conn.poll():
                cmd, val = conn.recv()
                if cmd == "EXPR": face.set_expression(val)
                elif cmd == "SPEAK": face._speaking = val
                elif cmd == "BLINK": face._auto_blink = val
                elif cmd == "STOP": running = False
            
            # Gestione Eventi Pygame
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: running = False

            face._update(dt)
            face._draw()
            pygame.display.flip()
        pygame.quit()

    def start(self):
        if not self._process or not self._process.is_alive():
            self._process = mp.Process(target=self._target, args=(self._child_conn, self._kwargs))
            self._process.daemon = True
            self._process.start()

    def stop(self):
        if self._process and self._process.is_alive():
            self._parent_conn.send(("STOP", None))
            self._process.join()

    def set_expression(self, expr: Expression):
        self._parent_conn.send(("EXPR", expr))

    def set_speaking(self, status: bool):
        self._parent_conn.send(("SPEAK", status))

# ====================================================================
# ESEMPIO DI UTILIZZO
# ====================================================================

if __name__ == "__main__":
    # Inizializza il manager (non blocca il thread principale)
    robot = RobotFaceManager(fullscreen=False, bg_color=(10, 10, 20))
    
    print("Avvio volto in processo dedicato...")
    robot.start()

    try:
        # Qui il thread principale è LIBERO di fare altro
        time.sleep(2)
        robot.set_expression(Expression.HAPPY)
        
        print("Il robot parla mentre il thread principale conta:")
        robot.set_speaking(True)
        
        for i in range(1, 6):
            print(f"Conto: {i}")
            time.sleep(1)
            if i == 3:
                robot.set_expression(Expression.ANGRY)
        
        robot.set_speaking(False)
        robot.set_expression(Expression.SLEEPING)
        time.sleep(2)

    except KeyboardInterrupt:
        pass
    finally:
        print("Chiusura in corso...")
        robot.stop()