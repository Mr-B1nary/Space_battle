import pygame
import random
import math
import json
import os
import sys

# ==================== راه‌اندازی اولیه ====================
pygame.init()
try:
    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
    AUDIO_OK = True
except Exception:
    AUDIO_OK = False

WIDTH, HEIGHT = 900, 650
FPS = 60
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Space Battle - National Competition")
clock = pygame.time.Clock()

# ==================== رنگ‌ها ====================
BLACK      = (8, 8, 18)
WHITE      = (240, 240, 255)
RED        = (255, 70, 70)
GREEN      = (70, 255, 120)
BLUE       = (80, 160, 255)
YELLOW     = (255, 220, 60)
PURPLE     = (200, 80, 255)
CYAN       = (80, 240, 255)
ORANGE     = (255, 140, 40)
DARK_RED   = (120, 30, 30)

# ==================== تولید صدا (Procedural) ====================
def make_sound(freq, duration, volume=0.3, wave='sine'):
    """تولید صدای ساده به صورت برنامه‌نویسی‌شده بدون فایل خارجی"""
    sample_rate = 22050
    n_samples = int(sample_rate * duration)
    data = []
    for i in range(n_samples):
        t = i / sample_rate
        if wave == 'sine':
            val = math.sin(2 * math.pi * freq * t)
        elif wave == 'square':
            val = 1.0 if math.sin(2 * math.pi * freq * t) > 0 else -1.0
        elif wave == 'noise':
            val = random.uniform(-1, 1)
        elif wave == 'saw':
            val = 2 * (t * freq - math.floor(0.5 + t * freq))
        else:
            val = math.sin(2 * math.pi * freq * t)
        env = max(0.0, 1 - (i / n_samples))  # محو شدن تدریجی
        sample = int(val * env * volume * 32767)
        b = sample.to_bytes(2, 'little', signed=True)
        data.append(b); data.append(b)  # استریو
    return pygame.mixer.Sound(buffer=b''.join(data))

if AUDIO_OK:
    try:
        shoot_sound     = make_sound(900, 0.06, 0.10, 'square')
        explosion_sound = make_sound(80, 0.35, 0.18, 'noise')
        powerup_sound   = make_sound(1400, 0.12, 0.15)
        hit_sound       = make_sound(150, 0.12, 0.15, 'noise')
        boss_sound      = make_sound(60, 0.6, 0.20, 'saw')
    except Exception:
        AUDIO_OK = False

def play(sound):
    if AUDIO_OK:
        try: sound.play()
        except Exception: pass

# ==================== کلاس Particle ====================
class Particle:
    def __init__(self, x, y, color, life=30, size=3):
        self.x, self.y = x, y
        self.color = color
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(1, 6)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = life
        self.max_life = life
        self.size = size

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.95
        self.vy *= 0.95
        self.life -= 1
        return self.life > 0

    def draw(self, surf):
        alpha = self.life / self.max_life
        s = max(1, int(self.size * alpha))
        color = tuple(min(255, int(c * alpha)) for c in self.color)
        pygame.draw.circle(surf, color, (int(self.x), int(self.y)), s)

# ==================== کلاس Bullet ====================
class Bullet:
    def __init__(self, x, y, vx, vy, color=YELLOW, damage=1, from_player=True, size=4):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.color = color
        self.damage = damage
        self.from_player = from_player
        self.size = size
        self.rect = pygame.Rect(0, 0, size * 2, size * 4)
        self.rect.center = (int(x), int(y))

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.rect.center = (int(self.x), int(self.y))

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.size)
        pygame.draw.circle(surf, WHITE, (int(self.x), int(self.y)), max(1, self.size - 2))

    def off_screen(self):
        return self.y < -30 or self.y > HEIGHT + 30 or self.x < -30 or self.x > WIDTH + 30

# ==================== کلاس Player ====================
class Player:
    def __init__(self):
        self.x = WIDTH // 2
        self.y = HEIGHT - 80
        self.speed = 6
        self.radius = 18
        self.lives = 3
        self.health = 100
        self.max_health = 100
        self.shield = 0
        self.rapid_fire = 0
        self.triple_shot = 0
        self.shoot_cooldown = 0
        self.invulnerable = 120
        self.rect = pygame.Rect(0, 0, 30, 30)
        self.rect.center = (int(self.x), int(self.y))

    def update(self, keys):
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: self.x -= self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: self.x += self.speed
        if keys[pygame.K_UP]    or keys[pygame.K_w]: self.y -= self.speed
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: self.y += self.speed
        self.x = max(self.radius, min(WIDTH - self.radius, self.x))
        self.y = max(self.radius + 60, min(HEIGHT - self.radius, self.y))
        self.rect.center = (int(self.x), int(self.y))
        for attr in ('shoot_cooldown', 'invulnerable', 'rapid_fire', 'triple_shot', 'shield'):
            v = getattr(self, attr)
            if v > 0: setattr(self, attr, v - 1)

    def shoot(self):
        if self.shoot_cooldown > 0: return []
        self.shoot_cooldown = 5 if self.rapid_fire > 0 else 12
        bullets = []
        if self.triple_shot > 0:
            bullets.append(Bullet(self.x,      self.y - 20,  0, -12, CYAN))
            bullets.append(Bullet(self.x - 12, self.y - 10, -2, -11, CYAN))
            bullets.append(Bullet(self.x + 12, self.y - 10,  2, -11, CYAN))
        else:
            bullets.append(Bullet(self.x - 8, self.y - 15, 0, -12, YELLOW))
            bullets.append(Bullet(self.x + 8, self.y - 15, 0, -12, YELLOW))
        return bullets

    def draw(self, surf):
        if self.invulnerable > 0 and (self.invulnerable // 4) % 2 == 0:
            return
        pts = [
            (self.x, self.y - self.radius - 5),
            (self.x - self.radius, self.y + self.radius),
            (self.x - self.radius // 2, self.y + self.radius // 2),
            (self.x, self.y + self.radius),
            (self.x + self.radius // 2, self.y + self.radius // 2),
            (self.x + self.radius, self.y + self.radius),
        ]
        pygame.draw.polygon(surf, CYAN, pts)
        pygame.draw.polygon(surf, WHITE, pts, 2)
        pygame.draw.circle(surf, BLUE, (int(self.x), int(self.y)), 6)
        pygame.draw.circle(surf, WHITE, (int(self.x), int(self.y)), 6, 1)
        # سپر
        if self.shield > 0:
            alpha = 100 + int(50 * math.sin(pygame.time.get_ticks() * 0.01))
            s = pygame.Surface((self.radius * 3, self.radius * 3), pygame.SRCALPHA)
            pygame.draw.circle(s, (80, 200, 255, alpha),
                               (self.radius * 3 // 2, self.radius * 3 // 2),
                               self.radius + 8, 3)
            surf.blit(s, (self.x - self.radius * 3 // 2, self.y - self.radius * 3 // 2))

# ==================== کلاس Enemy ====================
class Enemy:
    def __init__(self, x, y, kind='basic', level=1):
        self.x, self.y = x, y
        self.kind = kind
        self.level = level
        self.t = 0
        if kind == 'basic':
            self.hp = 1 + level // 3;   self.speed = 1.5 + level*0.1
            self.radius = 16; self.color = RED;      self.score = 10
        elif kind == 'zigzag':
            self.hp = 2 + level // 2;   self.speed = 1.8 + level*0.1
            self.radius = 18; self.color = PURPLE;   self.score = 20
        elif kind == 'shooter':
            self.hp = 3 + level // 2;   self.speed = 1.0 + level*0.05
            self.radius = 20; self.color = ORANGE;   self.score = 30
            self.shoot_timer = random.randint(60, 120)
        elif kind == 'tank':
            self.hp = 6 + level;        self.speed = 0.8
            self.radius = 26; self.color = DARK_RED; self.score = 50
        self.max_hp = self.hp
        self.start_x = x
        self.rect = pygame.Rect(0, 0, self.radius * 2, self.radius * 2)
        self.rect.center = (int(x), int(y))

    def update(self):
        self.t += 1
        if self.kind == 'basic':
            self.y += self.speed
        elif self.kind == 'zigzag':
            self.y += self.speed
            self.x = self.start_x + math.sin(self.t * 0.05) * 80
        elif self.kind == 'shooter':
            self.y += self.speed
            self.x += math.sin(self.t * 0.02) * 1.5
        elif self.kind == 'tank':
            self.y += self.speed
        self.rect.center = (int(self.x), int(self.y))

    def can_shoot(self):
        if self.kind != 'shooter': return False
        self.shoot_timer -= 1
        if self.shoot_timer <= 0:
            self.shoot_timer = random.randint(80, 150)
            return True
        return False

    def draw(self, surf):
        if self.kind == 'basic':
            pts = [(self.x, self.y - self.radius),
                   (self.x - self.radius, self.y + self.radius),
                   (self.x + self.radius, self.y + self.radius)]
            pygame.draw.polygon(surf, self.color, pts)
            pygame.draw.polygon(surf, WHITE, pts, 2)
        elif self.kind == 'zigzag':
            pts = [(self.x, self.y - self.radius), (self.x - self.radius, self.y),
                   (self.x, self.y + self.radius), (self.x + self.radius, self.y)]
            pygame.draw.polygon(surf, self.color, pts)
            pygame.draw.polygon(surf, WHITE, pts, 2)
        elif self.kind == 'shooter':
            pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.radius)
            pygame.draw.circle(surf, WHITE, (int(self.x), int(self.y)), self.radius, 2)
            pygame.draw.circle(surf, BLACK, (int(self.x), int(self.y)), self.radius // 2)
        elif self.kind == 'tank':
            r = pygame.Rect(self.x - self.radius, self.y - self.radius,
                            self.radius * 2, self.radius * 2)
            pygame.draw.rect(surf, self.color, r, border_radius=6)
            pygame.draw.rect(surf, WHITE, r, 2, border_radius=6)
        # نوار جان
        if self.hp < self.max_hp:
            bw, bh = self.radius * 2, 4
            bx, by = self.x - self.radius, self.y - self.radius - 10
            pygame.draw.rect(surf, DARK_RED, (bx, by, bw, bh))
            pygame.draw.rect(surf, GREEN, (bx, by, bw * self.hp / self.max_hp, bh))

# ==================== کلاس PowerUp ====================
class PowerUp:
    TYPES   = ['health', 'shield', 'rapid', 'triple']
    COLORS  = {'health': GREEN, 'shield': BLUE, 'rapid': YELLOW, 'triple': PURPLE}
    SYMBOLS = {'health': '+', 'shield': 'S', 'rapid': 'R', 'triple': 'T'}

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.kind = random.choice(self.TYPES)
        self.radius = 14
        self.t = 0
        self.vy = 2
        self.rect = pygame.Rect(0, 0, self.radius * 2, self.radius * 2)
        self.rect.center = (int(x), int(y))

    def update(self):
        self.t += 1
        self.y += self.vy
        self.x += math.sin(self.t * 0.08) * 1
        self.rect.center = (int(self.x), int(self.y))

    def draw(self, surf):
        color = self.COLORS[self.kind]
        a = 60 + int(40 * math.sin(self.t * 0.1))
        s = pygame.Surface((self.radius * 4, self.radius * 4), pygame.SRCALPHA)
        pygame.draw.circle(s, (*color, a), (self.radius * 2, self.radius * 2), self.radius + 8)
        surf.blit(s, (self.x - self.radius * 2, self.y - self.radius * 2))
        pygame.draw.circle(surf, color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surf, WHITE, (int(self.x), int(self.y)), self.radius, 2)
        font = pygame.font.SysFont('Arial', 16, bold=True)
        text = font.render(self.SYMBOLS[self.kind], True, BLACK)
        surf.blit(text, (self.x - text.get_width() // 2, self.y - text.get_height() // 2))

# ==================== کلاس Boss ====================
class Boss:
    def __init__(self, level):
        self.x = WIDTH // 2
        self.y = -100
        self.level = level
        self.max_hp = 50 + level * 30
        self.hp = self.max_hp
        self.radius = 60
        self.t = 0
        self.shoot_timer = 60
        self.entering = True
        self.rect = pygame.Rect(0, 0, self.radius * 2, self.radius * 2)
        self.rect.center = (int(self.x), int(self.y))
        self.score = 500 + level * 100

    def update(self):
        self.t += 1
        if self.entering:
            self.y += 1.5
            if self.y >= 120: self.entering = False
        else:
            self.x = WIDTH // 2 + math.sin(self.t * 0.02) * 250
            self.y = 120 + math.sin(self.t * 0.03) * 20
        self.rect.center = (int(self.x), int(self.y))

    def can_shoot(self):
        self.shoot_timer -= 1
        if self.shoot_timer <= 0:
            self.shoot_timer = max(20, 60 - self.level * 3)
            return True
        return False

    def draw(self, surf):
        pygame.draw.circle(surf, PURPLE, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surf, WHITE, (int(self.x), int(self.y)), self.radius, 3)
        pygame.draw.circle(surf, DARK_RED, (int(self.x), int(self.y)), self.radius // 2)
        for dx in (-25, 25):
            pygame.draw.circle(surf, RED, (int(self.x + dx), int(self.y - 10)), 10)
            pygame.draw.circle(surf, YELLOW, (int(self.x + dx), int(self.y - 10)), 4)
        # نوار جان بالای صفحه
        bw, bh = WIDTH - 100, 20
        bx, by = 50, 20
        pygame.draw.rect(surf, DARK_RED, (bx, by, bw, bh), border_radius=5)
        pygame.draw.rect(surf, RED, (bx, by, bw * self.hp / self.max_hp, bh), border_radius=5)
        pygame.draw.rect(surf, WHITE, (bx, by, bw, bh), 2, border_radius=5)
        font = pygame.font.SysFont('Arial', 16, bold=True)
        text = font.render(f"BOSS  {self.hp}/{self.max_hp}", True, WHITE)
        surf.blit(text, (WIDTH // 2 - text.get_width() // 2, by + 2))

# ==================== کلاس Star ====================
class Star:
    def __init__(self):
        self.x = random.randint(0, WIDTH)
        self.y = random.randint(0, HEIGHT)
        self.speed = random.uniform(0.5, 3)
        self.size = random.randint(1, 2)
        self.color = random.choice([WHITE, (180, 180, 220), (150, 200, 255)])

    def update(self):
        self.y += self.speed
        if self.y > HEIGHT:
            self.y = 0
            self.x = random.randint(0, WIDTH)

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.size)

# ==================== کلاس Game ====================
class Game:
    def __init__(self):
        self.high_score = self.load_high_score()
        self.reset()

    def reset(self):
        self.player = Player()
        self.bullets = []
        self.enemy_bullets = []
        self.enemies = []
        self.powerups = []
        self.particles = []
        self.boss = None
        self.stars = [Star() for _ in range(120)]
        self.score = 0
        self.level = 1
        self.wave = 0
        self.enemies_to_spawn = 0
        self.spawn_timer = 0
        self.state = 'menu'
        self.frame = 0
        self.boss_warning = 0
        self.between_waves = 0

    def load_high_score(self):
        try:
            with open('highscore.json', 'r') as f:
                return json.load(f).get('high', 0)
        except Exception:
            return 0

    def save_high_score(self):
        if self.score > self.high_score:
            self.high_score = self.score
            try:
                with open('highscore.json', 'w') as f:
                    json.dump({'high': self.high_score}, f)
            except Exception:
                pass

    def spawn_wave(self):
        self.wave += 1
        self.level = 1 + self.wave // 3
        if self.wave % 5 == 0:
            self.boss = Boss(self.wave // 5)
            self.boss_warning = 180
            play(boss_sound)
        else:
            self.enemies_to_spawn = 5 + self.wave * 2
            self.spawn_timer = 0
        self.between_waves = 60

    def spawn_enemy(self):
        if self.enemies_to_spawn <= 0: return
        self.enemies_to_spawn -= 1
        x = random.randint(60, WIDTH - 60)
        y = -40
        kinds = ['basic', 'basic', 'basic']
        if self.wave >= 2: kinds.append('zigzag')
        if self.wave >= 3: kinds.append('shooter')
        if self.wave >= 5: kinds.append('tank')
        self.enemies.append(Enemy(x, y, random.choice(kinds), self.level))

    def add_explosion(self, x, y, color, count=15):
        for _ in range(count):
            self.particles.append(Particle(x, y, color,
                                           life=random.randint(20, 40),
                                           size=random.randint(2, 4)))

    def apply_powerup(self, kind):
        if kind == 'health':
            self.player.health = min(self.player.max_health, self.player.health + 40)
        elif kind == 'shield':
            self.player.shield = 600
        elif kind == 'rapid':
            self.player.rapid_fire = 600
        elif kind == 'triple':
            self.player.triple_shot = 600

    def hit_player(self, damage):
        if self.player.shield > 0:
            self.player.shield = 0
            self.add_explosion(self.player.x, self.player.y, BLUE, 20)
            play(hit_sound)
            self.player.invulnerable = 60
            return
        self.player.health -= damage
        play(hit_sound)
        self.add_explosion(self.player.x, self.player.y, RED, 10)
        if self.player.health <= 0:
            self.player.lives -= 1
            self.add_explosion(self.player.x, self.player.y, ORANGE, 40)
            play(explosion_sound)
            if self.player.lives > 0:
                self.player.health = self.player.max_health
                self.player.invulnerable = 120
                self.player.x = WIDTH // 2
                self.player.y = HEIGHT - 80
            else:
                self.player.health = 0

    def update(self):
        self.frame += 1
        for s in self.stars: s.update()
        if self.state != 'playing': return

        keys = pygame.key.get_pressed()
        self.player.update(keys)

        # شلیک بازیکن
        if keys[pygame.K_SPACE]:
            new_bullets = self.player.shoot()
            if new_bullets:
                self.bullets.extend(new_bullets)
                play(shoot_sound)

        # به‌روزرسانی گلوله‌ها
        for b in self.bullets[:]:
            b.update()
            if b.off_screen(): self.bullets.remove(b)
        for b in self.enemy_bullets[:]:
            b.update()
            if b.off_screen(): self.enemy_bullets.remove(b)

        # Power-up ها
        for p in self.powerups[:]:
            p.update()
            if p.y > HEIGHT + 30:
                self.powerups.remove(p)
            elif p.rect.colliderect(self.player.rect):
                self.apply_powerup(p.kind)
                self.powerups.remove(p)
                play(powerup_sound)

        # دشمنان
        for e in self.enemies[:]:
            e.update()
            if e.y > HEIGHT + 50:
                self.enemies.remove(e); continue
            if e.can_shoot():
                dx = self.player.x - e.x
                dy = self.player.y - e.y
                d = max(1, math.hypot(dx, dy))
                self.enemy_bullets.append(
                    Bullet(e.x, e.y + e.radius, dx / d * 5, dy / d * 5,
                           RED, 1, False, 5))
            if self.player.invulnerable == 0 and e.rect.colliderect(self.player.rect):
                self.hit_player(15)
                self.add_explosion(e.x, e.y, e.color, 15)
                if e in self.enemies: self.enemies.remove(e)

        # غول
        if self.boss:
            self.boss.update()
            if self.boss.can_shoot() and not self.boss.entering:
                pattern = (self.boss.t // 200) % 3
                if pattern == 0:
                    for ang in range(0, 360, 30):
                        r = math.radians(ang)
                        self.enemy_bullets.append(
                            Bullet(self.boss.x, self.boss.y,
                                   math.cos(r) * 4, math.sin(r) * 4, PURPLE, 1, False, 6))
                elif pattern == 1:
                    dx = self.player.x - self.boss.x
                    dy = self.player.y - self.boss.y
                    base = math.atan2(dy, dx)
                    for off in (-0.2, 0, 0.2):
                        a = base + off
                        self.enemy_bullets.append(
                            Bullet(self.boss.x, self.boss.y,
                                   math.cos(a) * 6, math.sin(a) * 6, RED, 1, False, 6))
                else:
                    for i in range(5):
                        self.enemy_bullets.append(
                            Bullet(self.boss.x + (i - 2) * 30, self.boss.y,
                                   0, 5, ORANGE, 1, False, 7))
            if self.player.invulnerable == 0 and self.boss.rect.colliderect(self.player.rect):
                self.hit_player(20)

        # برخورد گلوله بازیکن با دشمنان / غول
        for b in self.bullets[:]:
            hit = False
            for e in self.enemies[:]:
                if b.rect.colliderect(e.rect):
                    e.hp -= b.damage
                    self.add_explosion(b.x, b.y, YELLOW, 4)
                    if e.hp <= 0:
                        self.score += e.score
                        self.add_explosion(e.x, e.y, e.color, 20)
                        play(explosion_sound)
                        self.enemies.remove(e)
                        if random.random() < 0.12:
                            self.powerups.append(PowerUp(e.x, e.y))
                    hit = True; break
            if not hit and self.boss and not self.boss.entering:
                if b.rect.colliderect(self.boss.rect):
                    self.boss.hp -= b.damage
                    self.add_explosion(b.x, b.y, CYAN, 4)
                    hit = True
                    if self.boss.hp <= 0:
                        self.score += self.boss.score
                        self.add_explosion(self.boss.x, self.boss.y, PURPLE, 60)
                        self.add_explosion(self.boss.x, self.boss.y, RED, 40)
                        play(explosion_sound)
                        self.boss = None
            if hit and b in self.bullets:
                self.bullets.remove(b)

        # برخورد گلوله دشمن با بازیکن
        for b in self.enemy_bullets[:]:
            if self.player.invulnerable == 0 and b.rect.colliderect(self.player.rect):
                self.hit_player(10)
                self.enemy_bullets.remove(b)

        # ذرات
        for p in self.particles[:]:
            if not p.update(): self.particles.remove(p)

        # مدیریت موج‌ها
        if not self.boss and self.enemies_to_spawn <= 0 and not self.enemies:
            if self.between_waves > 0:
                self.between_waves -= 1
            else:
                self.spawn_wave()
        elif self.enemies_to_spawn > 0:
            self.spawn_timer -= 1
            if self.spawn_timer <= 0:
                self.spawn_enemy()
                self.spawn_timer = max(20, 60 - self.wave * 2)

        if self.boss_warning > 0: self.boss_warning -= 1

        if self.player.lives <= 0:
            self.state = 'gameover'
            self.save_high_score()

    # ==================== رسم ====================
    def draw(self, surf):
        surf.fill(BLACK)
        for s in self.stars: s.draw(surf)

        if self.state == 'menu':
            self.draw_menu(surf); return

        for p in self.powerups: p.draw(surf)
        for e in self.enemies:  e.draw(surf)
        if self.boss: self.boss.draw(surf)
        for b in self.bullets: b.draw(surf)
        for b in self.enemy_bullets: b.draw(surf)
        for p in self.particles: p.draw(surf)
        if self.player.lives > 0:
            self.player.draw(surf)

        self.draw_ui(surf)

        if self.boss_warning > 0 and (self.boss_warning // 10) % 2 == 0:
            font = pygame.font.SysFont('Arial', 60, bold=True)
            t = font.render("WARNING! BOSS!", True, RED)
            surf.blit(t, (WIDTH // 2 - t.get_width() // 2, HEIGHT // 2 - 50))

        if self.state == 'paused':      self.draw_pause(surf)
        elif self.state == 'gameover':  self.draw_gameover(surf)

    def draw_ui(self, surf):
        font = pygame.font.SysFont('Arial', 20, bold=True)
        surf.blit(font.render(f"Score: {self.score}", True, WHITE), (15, 50))
        surf.blit(font.render(f"High: {max(self.high_score, self.score)}",
                              True, YELLOW), (15, 75))
        surf.blit(font.render(f"Wave: {self.wave}", True, CYAN), (WIDTH - 150, 50))
        # جان‌ها
        for i in range(self.player.lives):
            pygame.draw.polygon(surf, CYAN, [
                (20 + i * 30, HEIGHT - 30),
                (10 + i * 30, HEIGHT - 10),
                (30 + i * 30, HEIGHT - 10)])
        # نوار جان
        bw, bh = 200, 18
        bx, by = 15, HEIGHT - 60
        pygame.draw.rect(surf, DARK_RED, (bx, by, bw, bh), border_radius=4)
        hp = int(bw * max(0, self.player.health) / self.player.max_health)
        col = GREEN if self.player.health > 50 else (YELLOW if self.player.health > 25 else RED)
        pygame.draw.rect(surf, col, (bx, by, hp, bh), border_radius=4)
        pygame.draw.rect(surf, WHITE, (bx, by, bw, bh), 2, border_radius=4)
        # پاوراپ‌های فعال
        y = HEIGHT - 90
        if self.player.shield > 0:
            surf.blit(font.render(f"Shield: {self.player.shield // 60}s", True, BLUE), (bx, y)); y -= 25
        if self.player.rapid_fire > 0:
            surf.blit(font.render(f"Rapid: {self.player.rapid_fire // 60}s", True, YELLOW), (bx, y)); y -= 25
        if self.player.triple_shot > 0:
            surf.blit(font.render(f"Triple: {self.player.triple_shot // 60}s", True, PURPLE), (bx, y)); y -= 25

    def draw_menu(self, surf):
        big = pygame.font.SysFont('Arial', 72, bold=True)
        t = big.render("SPACE BATTLE", True, CYAN)
        surf.blit(t, (WIDTH // 2 - t.get_width() // 2, 100))

        tt = pygame.time.get_ticks() * 0.001
        y = 270 + math.sin(tt * 2) * 10
        pygame.draw.polygon(surf, CYAN, [
            (WIDTH // 2, y - 30), (WIDTH // 2 - 30, y + 30),
            (WIDTH // 2, y + 15), (WIDTH // 2 + 30, y + 30)])
        pygame.draw.circle(surf, BLUE, (WIDTH // 2, y), 8)

        mid = pygame.font.SysFont('Arial', 28, bold=True)
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            s = mid.render("Press SPACE to Start", True, WHITE)
            surf.blit(s, (WIDTH // 2 - s.get_width() // 2, 390))

        small = pygame.font.SysFont('Arial', 20)
        lines = [
            "Controls:",
            "WASD / Arrows  -  Move",
            "SPACE  -  Shoot",
            "P  -  Pause     ESC  -  Quit",
            "",
            f"High Score: {self.high_score}",
        ]
        for i, line in enumerate(lines):
            tx = small.render(line, True, (200, 200, 220))
            surf.blit(tx, (WIDTH // 2 - tx.get_width() // 2, 460 + i * 26))

    def draw_pause(self, surf):
        o = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        o.fill((0, 0, 0, 150)); surf.blit(o, (0, 0))
        big = pygame.font.SysFont('Arial', 60, bold=True)
        t = big.render("PAUSED", True, WHITE)
        surf.blit(t, (WIDTH // 2 - t.get_width() // 2, HEIGHT // 2 - 60))
        s = pygame.font.SysFont('Arial', 24).render("Press P to Resume", True, WHITE)
        surf.blit(s, (WIDTH // 2 - s.get_width() // 2, HEIGHT // 2 + 20))

    def draw_gameover(self, surf):
        o = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        o.fill((0, 0, 0, 180)); surf.blit(o, (0, 0))
        big = pygame.font.SysFont('Arial', 64, bold=True)
        t = big.render("GAME OVER", True, RED)
        surf.blit(t, (WIDTH // 2 - t.get_width() // 2, 150))
        f = pygame.font.SysFont('Arial', 32, bold=True)
        for i, (txt, c) in enumerate([
            (f"Score: {self.score}", WHITE),
            (f"High Score: {self.high_score}", YELLOW),
            (f"Wave Reached: {self.wave}", CYAN),
        ]):
            s = f.render(txt, True, c)
            surf.blit(s, (WIDTH // 2 - s.get_width() // 2, 260 + i * 50))
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            s = pygame.font.SysFont('Arial', 24).render(
                "Press R to Restart | ESC to Quit", True, WHITE)
            surf.blit(s, (WIDTH // 2 - s.get_width() // 2, 450))

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN: return
        if self.state == 'menu' and event.key == pygame.K_SPACE:
            self.reset(); self.state = 'playing'; self.spawn_wave()
        elif self.state == 'playing' and event.key == pygame.K_p:
            self.state = 'paused'
        elif self.state == 'paused' and event.key == pygame.K_p:
            self.state = 'playing'
        elif self.state == 'gameover' and event.key == pygame.K_r:
            self.reset(); self.state = 'playing'; self.spawn_wave()

# ==================== حلقه اصلی ====================
def main():
    game = Game()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            else:
                game.handle_event(event)
        game.update()
        game.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()