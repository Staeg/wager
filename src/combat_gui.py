import tkinter as tk
import math
import os
from PIL import Image, ImageTk, ImageEnhance
from .compat import get_asset_dir
from .constants import (
    COMBAT_P1_ZONE_END,
    COMBAT_P2_ZONE_START,
    HEX_COL_SPACING,
    HEX_ROW_SPACING,
    HEX_ODD_ROW_OFFSET,
    HEX_POLYGON_SCALE,
)
from .combat import Battle
from .heroes import HERO_STATS
from .hex import hex_distance


# --- GUI ---


def format_ability(ability, include_self_target=False):
    parts = []
    aura = ability.get("aura")
    if aura:
        parts.append(f"Aura {aura}")
    charge = ability.get("charge")
    if charge:
        parts.append(f"Charge {charge}")
    trigger = ability.get("trigger")
    if trigger:
        parts.append(trigger.capitalize())
    target = ability.get("target")
    if target and (target != "self" or include_self_target):
        parts.append(target.capitalize())
    rng = ability.get("range")
    value = ability.get("value")
    # Show range after target if no value (e.g., "Area 2 Silence")
    if rng is not None and value is None:
        parts.append(str(rng))
    effect = ability.get("effect", "").replace("_", " ").title()
    if effect:
        parts.append(effect)
    if value is not None:
        if rng is not None:
            parts.append(f"{value}/{rng}")
        else:
            parts.append(str(value))
    count = ability.get("count")
    if count is not None and ability.get("effect") == "summon":
        parts.append(f"x{count}")
    return " ".join(parts)


def describe_ability(ability):
    trigger = ability.get("trigger")
    effect = ability.get("effect")
    target = ability.get("target", "self")
    value = ability.get("value")
    rng = ability.get("range")
    aura = ability.get("aura")
    count = ability.get("count")
    charge = ability.get("charge")
    range_text = f"{rng} range" if rng is not None else "attack range"
    aura_text = "attack range" if aura == "R" else f"{aura} range" if aura else "aura"

    if charge:
        if trigger in ("endturn", "turnstart"):
            prefix = f"Every {charge} turns, "
        elif trigger == "onhit":
            prefix = f"Every {charge} hits, "
        elif trigger == "onkill":
            prefix = f"Every {charge} kills, "
        elif trigger == "wounded":
            prefix = f"Every {charge} times this unit is damaged, "
        elif trigger == "lament":
            prefix = f"Every {charge} allies that die within {range_text}, "
        elif trigger == "harvest":
            prefix = f"Every {charge} enemies that die within {range_text}, "
        else:
            prefix = f"Every {charge} triggers, "
    else:
        if trigger == "endturn":
            prefix = "At end of turn, "
        elif trigger == "turnstart":
            prefix = "At start of turn, "
        elif trigger == "onhit":
            prefix = "After attacking, "
        elif trigger == "onkill":
            prefix = "After killing an enemy, "
        elif trigger == "wounded":
            prefix = "When this unit is damaged, "
        elif trigger == "lament":
            prefix = f"When an ally dies within {range_text}, "
        elif trigger == "harvest":
            prefix = f"When an enemy dies within {range_text}, "
        elif trigger == "passive":
            prefix = ""
        else:
            prefix = ""

    if effect == "armor":
        if aura:
            return f"Allies within {aura_text} gain {value} armor (reduces damage by {value})."
        return f"Reduces all damage taken by {value}."
    if effect == "amplify":
        return f"Allied ability values within {aura_text} are increased by {value}."
    if effect == "boost":
        return f"All allied units gain +{value} attack damage."
    if effect == "undying":
        return f"Allies within {aura_text} that would die instead lose {value} attack damage."
    if effect == "lament_aura":
        return f"Allies within {aura_text} gain {value} attack damage when an ally within {rng} of them dies."
    if effect == "ramp":
        return f"{prefix}gain {value} attack damage."
    if effect == "push":
        return f"{prefix}push the attacked target {value} hex{'es' if value != 1 else ''} horizontally if possible."
    if effect == "retreat":
        return f"{prefix}move 1 hex away from the attacked target."
    if effect == "freeze":
        return f"{prefix}exhaust {value} random ready enemies within attack range."
    if effect == "splash":
        return (
            f"{prefix}deal {value} damage to enemies adjacent to the attacked target."
        )
    if effect == "heal":
        if target == "self":
            return f"{prefix}heal {value} HP."
        if target == "random":
            return f"{prefix}heal a random ally within {range_text} for {value} HP."
        if target == "area":
            return f"{prefix}heal all allies within {range_text} for {value} HP."
    if effect == "fortify":
        if target == "area":
            return f"{prefix}grant {value} max and current HP to all allies within {range_text}."
        return f"{prefix}grant {value} max and current HP."
    if effect == "sunder":
        if target == "random":
            return f"{prefix}reduce armor of a random enemy within {range_text} by {value}."
        if target == "area":
            return (
                f"{prefix}reduce armor of all enemies within {range_text} by {value}."
            )
        if target == "target":
            return f"{prefix}reduce armor of the attacked enemy by {value}."
    if effect == "strike":
        if target == "random":
            return f"{prefix}deal {value} damage to a random enemy within {range_text}."
        if target == "area":
            return f"{prefix}deal {value} damage to all enemies within {range_text}."
        if target == "target":
            return f"{prefix}deal {value} damage to the attacked enemy."
    if effect == "summon":
        count_val = count or 1
        target_hint = "adjacent to the summoner"
        if ability.get("summon_target") == "highest":
            target_hint = f"adjacent to the highest-health ally within {range_text}"
        ready_hint = (
            "They are ready." if ability.get("summon_ready") else "They are exhausted."
        )
        return f"{prefix}summon {count_val} Blade{'s' if count_val != 1 else ''} {target_hint}. {ready_hint}"
    if effect == "shadowstep":
        return f"{prefix}teleport adjacent to the furthest enemy instead of moving."
    if effect == "block":
        return f"Reduces the first {value} damage instances each round to 0."
    if effect == "silence":
        return f"{prefix}disable all abilities of enemies within {range_text}."
    if effect == "execute":
        return (
            f"Enemies within {aura_text} that fall to {value} HP or below are killed."
        )
    if effect == "ready":
        return f"{prefix}become ready to act again this round."

    return format_ability(ability)


def bind_keyword_hover(label, parent, description):
    sub_tip = [None]

    def on_enter(e):
        sub_tip[0] = st = tk.Toplevel(parent)
        st.wm_overrideredirect(True)
        st.wm_geometry(f"+{e.x_root + 10}+{e.y_root + 18}")
        tk.Label(
            st,
            text=description,
            fg="white",
            bg="#444",
            font=("Arial", 9),
            padx=4,
            pady=2,
        ).pack()

    def on_leave(e):
        if sub_tip[0]:
            sub_tip[0].destroy()
            sub_tip[0] = None

    label.bind("<Enter>", on_enter)
    label.bind("<Leave>", on_leave)


class CombatGUI:
    HEX_SIZE = 32

    def __init__(
        self,
        root,
        battle=None,
        on_complete=None,
        attacker_player=None,
        defender_player=None,
    ):
        self.root = root
        try:
            root.title("Wager of War v3 - Combat")
        except AttributeError:
            pass
        self.battle = battle if battle is not None else Battle()
        self.battle.apply_events_immediately = False
        self.on_complete = on_complete
        self.attacker_player = attacker_player
        self.defender_player = defender_player

        # layout
        top = tk.Frame(root)
        top.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.step_btn = tk.Button(
            top, text="Step", command=self.on_step, font=("Arial", 12)
        )
        self.step_btn.pack(side=tk.LEFT)

        self.auto_btn = tk.Button(
            top, text="Auto", command=self.toggle_auto, font=("Arial", 12)
        )
        self.auto_btn.pack(side=tk.LEFT, padx=5)

        # Speed controls
        self.speed_levels = [
            (300, "0.3x"),
            (200, "0.5x"),
            (100, "1x"),
            (50, "2x"),
            (25, "4x"),
        ]
        self.speed_index = 2
        self.auto_delay = self.speed_levels[self.speed_index][0]

        self.speed_down_btn = tk.Button(
            top, text="-", command=self._speed_down, font=("Arial", 12), width=2
        )
        self.speed_down_btn.pack(side=tk.LEFT)
        self.speed_var = tk.StringVar(value=self.speed_levels[self.speed_index][1])
        tk.Label(top, textvariable=self.speed_var, font=("Arial", 11), width=4).pack(
            side=tk.LEFT
        )
        self.speed_up_btn = tk.Button(
            top, text="+", command=self._speed_up, font=("Arial", 12), width=2
        )
        self.speed_up_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.undo_btn = tk.Button(
            top, text="Undo", command=self.on_undo, font=("Arial", 12)
        )
        self.undo_btn.pack(side=tk.LEFT, padx=5)

        self.skip_btn = tk.Button(
            top, text="Skip", command=self.on_skip, font=("Arial", 12)
        )
        self.skip_btn.pack(side=tk.LEFT, padx=5)

        self.reset_btn = tk.Button(
            top, text="Reset", command=self.on_reset, font=("Arial", 12)
        )
        self.reset_btn.pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Round 1")
        tk.Label(top, textvariable=self.status_var, font=("Arial", 12)).pack(
            side=tk.LEFT, padx=15
        )

        self.score_var = tk.StringVar()
        tk.Label(top, textvariable=self.score_var, font=("Arial", 11)).pack(
            side=tk.RIGHT
        )

        canvas_w = self._hex_x(self.battle.COLS, 0) + self.HEX_SIZE + 20
        canvas_h = self._hex_y(0, self.battle.ROWS) + self.HEX_SIZE + 20
        self.canvas = tk.Canvas(root, width=canvas_w, height=canvas_h, bg="#2b2b2b")
        self.canvas.pack(padx=5, pady=5)

        self.log_btn = tk.Button(
            top, text="Log", command=self._toggle_log, font=("Arial", 12)
        )
        self.log_btn.pack(side=tk.LEFT, padx=5)

        self._log_window = None
        self.log_text = None

        self.return_btn = None
        self.auto_running = False
        self._tooltip = None
        self._tooltip_unit = None
        self.canvas.bind("<Motion>", self._on_hover)
        self.canvas.bind("<Leave>", self._on_leave)
        root.bind("<KeyRelease-Shift_L>", self._on_shift_release)
        root.bind("<KeyRelease-Shift_R>", self._on_shift_release)
        self._load_sprites()
        self._draw()

    def _load_sprites(self):
        asset_dir = get_asset_dir()
        self._sprite_imgs = {}
        for name in (
            "footman",
            "archer",
            "priest",
            "knight",
            "mage",
            "page",
            "librarian",
            "steward",
            "gatekeeper",
            "apprentice",
            "conduit",
            "seeker",
            "savant",
            "tincan",
            "golem",
            "kitboy",
            "artillery",
            "penitent",
            "avenger",
            "herald",
            "blade",
            "watcher",
            "neophyte",
            "accursed",
            "enchantress",
            "prodigy",
            "scholar",
            "outcast",
            "mercenary",
            "tactician",
            "maiden",
            "aspirant",
            "apostle",
        ):
            img = Image.open(os.path.join(asset_dir, f"{name}.png")).convert("RGBA")
            bright = img
            faded = ImageEnhance.Brightness(img).enhance(0.5)
            self._sprite_imgs[name] = (bright, faded)
        self._sprite_cache = {}

    def _get_sprite(self, name, faded):
        key = (name, faded)
        if key not in self._sprite_cache:
            img = self._sprite_imgs[name][1 if faded else 0]
            self._sprite_cache[key] = ImageTk.PhotoImage(img)
        return self._sprite_cache[key]

    def _hex_x(self, col, row):
        x = self.HEX_SIZE * HEX_COL_SPACING * col + 30
        if row % 2 == 1:
            x += self.HEX_SIZE * HEX_ODD_ROW_OFFSET
        return x

    def _hex_y(self, col, row):
        return self.HEX_SIZE * HEX_ROW_SPACING * row + 30

    def _hex_polygon(self, cx, cy):
        points = []
        for i in range(6):
            angle = math.radians(60 * i + 30)
            points.append(cx + self.HEX_SIZE * HEX_POLYGON_SCALE * math.cos(angle))
            points.append(cy + self.HEX_SIZE * HEX_POLYGON_SCALE * math.sin(angle))
        return points

    def _draw(self):
        self.canvas.delete("all")
        b = self.battle

        # draw grid
        for r in range(b.ROWS):
            for c in range(b.COLS):
                cx = self._hex_x(c, r)
                cy = self._hex_y(c, r)
                if c < COMBAT_P1_ZONE_END:
                    fill = "#3a3a5c"
                elif c >= COMBAT_P2_ZONE_START:
                    fill = "#5c3a3a"
                else:
                    fill = "#3a3a3a"
                self.canvas.create_polygon(
                    self._hex_polygon(cx, cy), fill=fill, outline="#555"
                )

        # draw aura glows behind units
        for u in b.units:
            if not u.alive:
                continue
            aura_specs = []
            for ab in u.abilities:
                if ab.get("trigger") != "passive":
                    continue
                aura_range = ab.get("aura")
                if not aura_range:
                    continue
                if aura_range == "R":
                    aura_range = u.attack_range
                if ab.get("effect") == "amplify":
                    aura_specs.append((aura_range, "#8844cc"))  # purple for amplify
                elif ab.get("effect") == "undying":
                    aura_specs.append((aura_range, "#ccaa22"))  # gold for undying
                elif ab.get("effect") == "armor":
                    aura_specs.append((aura_range, "#5aa7ff"))  # blue for armor aura
            for aura_range, aura_color in aura_specs:
                # Draw faint highlight on all hexes within aura range
                for r2 in range(b.ROWS):
                    for c2 in range(b.COLS):
                        if (
                            hex_distance(u.pos, (c2, r2)) <= aura_range
                            and (c2, r2) != u.pos
                        ):
                            ax = self._hex_x(c2, r2)
                            ay = self._hex_y(c2, r2)
                            self.canvas.create_polygon(
                                self._hex_polygon(ax, ay),
                                fill="",
                                outline=aura_color,
                                width=2,
                                stipple="gray25",
                            )

        # draw units
        self._sprite_refs = []  # prevent GC
        for u in b.units:
            if not u.alive:
                continue
            cx = self._hex_x(u.pos[0], u.pos[1])
            cy = self._hex_y(u.pos[0], u.pos[1])
            sprite_name = u.name.lower()
            sprite = self._get_sprite(sprite_name, u.has_acted)
            self._sprite_refs.append(sprite)
            self.canvas.create_image(cx, cy, image=sprite)
            if u.name in HERO_STATS:
                self._draw_crown(cx, cy)

            # HP bar
            bar_w = self.HEX_SIZE * 0.7
            bar_h = 4
            hp_frac = u.hp / u.max_hp
            bx = cx - bar_w / 2
            by = cy - 18
            self.canvas.create_rectangle(
                bx, by, bx + bar_w, by + bar_h, fill="#333", outline=""
            )
            bar_color = (
                "#44ff44"
                if hp_frac > 0.5
                else "#ffaa00"
                if hp_frac > 0.25
                else "#ff4444"
            )
            self.canvas.create_rectangle(
                bx, by, bx + bar_w * hp_frac, by + bar_h, fill=bar_color, outline=""
            )

        # update status
        p1_counts = {}
        p2_counts = {}
        for u in b.units:
            if not u.alive:
                continue
            d = p1_counts if u.player == 1 else p2_counts
            d[u.name] = d.get(u.name, 0) + 1
        p1_str = "  ".join(f"{n}:{c}" for n, c in p1_counts.items())
        p2_str = "  ".join(f"{n}:{c}" for n, c in p2_counts.items())
        left_label = (
            f"Attacker: {self.attacker_player}" if self.attacker_player else "Attacker"
        )
        right_label = (
            f"Defender: {self.defender_player}" if self.defender_player else "Defender"
        )
        self.score_var.set(f"{left_label} [{p1_str}]  |  {right_label} [{p2_str}]")
        if b.winner is not None:
            if b.winner == 0:
                self.status_var.set("Stalemate - Draw!")
            else:
                self.status_var.set(f"Player {b.winner} wins!")
            if self.on_complete:
                if not self.return_btn:
                    p1_survivors = sum(1 for u in b.units if u.alive and u.player == 1)
                    p2_survivors = sum(1 for u in b.units if u.alive and u.player == 2)
                    self.return_btn = tk.Button(
                        self.canvas,
                        text="Return to Overworld",
                        font=("Arial", 14),
                        command=lambda: self.on_complete(
                            b.winner, p1_survivors, p2_survivors
                        ),
                    )
                self.canvas.create_window(
                    self.canvas.winfo_reqwidth() // 2,
                    self.canvas.winfo_reqheight() // 2,
                    window=self.return_btn,
                )
        else:
            self.status_var.set(f"Round {b.round_num}")
            if self.return_btn:
                self.return_btn.destroy()
                self.return_btn = None

        # update log
        self._update_log_display()

    def _draw_crown(self, cx, cy):
        """Draw a small crown at the top-left of the unit's hex."""
        x = cx - self.HEX_SIZE * 0.65
        y = cy - self.HEX_SIZE * 0.85
        points = [
            x + 0,
            y + 6,
            x + 2,
            y + 0,
            x + 4,
            y + 6,
            x + 6,
            y + 0,
            x + 8,
            y + 6,
            x + 10,
            y + 2,
            x + 10,
            y + 10,
            x + 0,
            y + 10,
        ]
        self.canvas.create_polygon(points, fill="#f1d44c", outline="#b48b1a")

    def _unit_at_pixel(self, px, py):
        """Return the unit closest to pixel coords, if within hex radius."""
        best_unit = None
        best_dist = float("inf")
        for u in self.battle.units:
            if not u.alive:
                continue
            cx = self._hex_x(u.pos[0], u.pos[1])
            cy = self._hex_y(u.pos[0], u.pos[1])
            d = math.hypot(px - cx, py - cy)
            if d < self.HEX_SIZE * 0.8 and d < best_dist:
                best_dist = d
                best_unit = u
        return best_unit

    def _on_hover(self, event):
        unit = self._unit_at_pixel(event.x, event.y)
        shift_held = event.state & 0x1
        if unit:
            if self._tooltip_unit is unit and self._tooltip is not None:
                if not shift_held:
                    self._tooltip.wm_geometry(
                        f"+{event.x_root + 15}+{event.y_root + 10}"
                    )
                return
            self._hide_tooltip()
            self._tooltip_unit = unit
            self._tooltip = tw = tk.Toplevel(self.root)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{event.x_root + 15}+{event.y_root + 10}")
            tw.configure(bg="#222")

            main_text = f"{unit.display_name} (P{unit.player})  HP: {unit.hp}/{unit.max_hp}  Dmg:{unit.damage}  Rng:{unit.attack_range}"
            if unit.speed > 1.0:
                main_text += f"  Spd:{unit.speed}"
            tk.Label(
                tw,
                text=main_text,
                fg="white",
                bg="#222",
                font=("Arial", 10, "bold"),
                padx=6,
                pady=2,
            ).pack(anchor="w")

            if unit.abilities:
                row = tk.Frame(tw, bg="#222")
                row.pack(anchor="w", padx=4, pady=(0, 2))
                for ability in unit.abilities:
                    text = format_ability(ability)
                    description = describe_ability(ability)
                    lbl = tk.Label(
                        row,
                        text=text,
                        fg="#aaffaa",
                        bg="#333",
                        font=("Arial", 9),
                        padx=4,
                        pady=1,
                        relief=tk.RAISED,
                        borderwidth=1,
                    )
                    lbl.pack(side=tk.LEFT, padx=2)
                    self._bind_ability_hover(lbl, tw, description)
        else:
            if not shift_held:
                self._hide_tooltip()

    def _bind_ability_hover(self, label, parent, description):
        bind_keyword_hover(label, parent, description)

    def _on_leave(self, event):
        shift_held = event.state & 0x1
        if not shift_held:
            self._hide_tooltip()

    def _on_shift_release(self, event):
        # Check if cursor is still over a unit
        try:
            mx = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
            my = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
            if not self._unit_at_pixel(mx, my):
                self._hide_tooltip()
        except Exception:
            self._hide_tooltip()

    def _update_log_display(self):
        if self.log_text is None:
            return
        try:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete("1.0", tk.END)
            for line in self.battle.log[-50:]:
                self.log_text.insert(tk.END, line + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        except tk.TclError:
            pass  # window was closed

    def _toggle_log(self):
        """Toggle the battle log popout window."""
        if self._log_window and self._log_window.winfo_exists():
            self._log_window.destroy()
            self._log_window = None
            self.log_text = None
            return
        self._log_window = lw = tk.Toplevel(self.root)
        lw.title("Battle Log")
        lw.geometry("500x300")
        lw.transient(self.root)
        self.log_text = tk.Text(lw, font=("Consolas", 9), state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self._update_log_display()

    def _close_log(self):
        """Close the log window if open."""
        if self._log_window and self._log_window.winfo_exists():
            self._log_window.destroy()
        self._log_window = None
        self.log_text = None

    def _hide_tooltip(self):
        if self._tooltip is not None:
            self._tooltip.destroy()
            self._tooltip = None
            self._tooltip_unit = None

    def _anim_delay(self, base_ms):
        """Scale animation delay by current speed setting (1x = 100ms auto_delay)."""
        return max(1, int(base_ms * self.auto_delay / 100))

    def _animate_arrow(self, src, dst, on_done, frame=0):
        """Animate an arrow projectile from src to dst hex over several frames."""
        total_frames = 8
        if frame > total_frames:
            self.canvas.delete("anim")
            on_done()
            return

        t = frame / total_frames
        sx, sy = self._hex_x(src[0], src[1]), self._hex_y(src[0], src[1])
        dx, dy = self._hex_x(dst[0], dst[1]), self._hex_y(dst[0], dst[1])
        cx = sx + (dx - sx) * t
        cy = sy + (dy - sy) * t

        self.canvas.delete("anim")
        # Arrow: a line with a triangle head
        angle = math.atan2(dy - sy, dx - sx)
        tail_x = cx - 10 * math.cos(angle)
        tail_y = cy - 10 * math.sin(angle)
        self.canvas.create_line(
            tail_x, tail_y, cx, cy, fill="#ffff44", width=2, tags="anim"
        )
        # Arrowhead
        ha1 = angle + math.radians(150)
        ha2 = angle - math.radians(150)
        self.canvas.create_polygon(
            cx,
            cy,
            cx + 6 * math.cos(ha1),
            cy + 6 * math.sin(ha1),
            cx + 6 * math.cos(ha2),
            cy + 6 * math.sin(ha2),
            fill="#ffff44",
            tags="anim",
        )
        self.root.after(
            self._anim_delay(30),
            lambda: self._animate_arrow(src, dst, on_done, frame + 1),
        )

    def _animate_slash(self, target_pos, attacker_pos, on_done, frame=0):
        """Animate a slash effect offset 25% from target toward attacker."""
        total_frames = 6
        if frame > total_frames:
            self.canvas.delete("anim")
            on_done()
            return

        tx = self._hex_x(target_pos[0], target_pos[1])
        ty = self._hex_y(target_pos[0], target_pos[1])
        ax = self._hex_x(attacker_pos[0], attacker_pos[1])
        ay = self._hex_y(attacker_pos[0], attacker_pos[1])
        # Place slash 40% of the way from target toward attacker
        cx = tx + (ax - tx) * 0.4
        cy = ty + (ay - ty) * 0.4
        self.canvas.delete("anim")

        t = frame / total_frames
        r = self.HEX_SIZE * 0.4
        sweep = -60 + 120 * t
        angle = math.radians(sweep)
        x1 = cx + r * math.cos(angle)
        y1 = cy + r * math.sin(angle)
        x2 = cx - r * math.cos(angle)
        y2 = cy - r * math.sin(angle)
        gb = int(255 * (1 - t))
        color = f"#ff{gb:02x}{gb:02x}"
        self.canvas.create_line(x1, y1, x2, y2, fill=color, width=3, tags="anim")
        angle2 = math.radians(sweep + 30)
        x3 = cx + r * 0.7 * math.cos(angle2)
        y3 = cy + r * 0.7 * math.sin(angle2)
        x4 = cx - r * 0.7 * math.cos(angle2)
        y4 = cy - r * 0.7 * math.sin(angle2)
        self.canvas.create_line(x3, y3, x4, y4, fill=color, width=2, tags="anim")

        self.root.after(
            self._anim_delay(40),
            lambda: self._animate_slash(target_pos, attacker_pos, on_done, frame + 1),
        )

    def _animate_heal(self, pos, on_done, frame=0):
        """Animate a green '+' that fades at the given hex position."""
        total_frames = 10
        if frame > total_frames:
            self.canvas.delete("heal_anim")
            on_done()
            return
        t = frame / total_frames
        cx = self._hex_x(pos[0], pos[1])
        cy = self._hex_y(pos[0], pos[1]) - t * 12  # float upward
        alpha = int(255 * (1 - t))
        green = f"#00{alpha:02x}00"
        self.canvas.delete("heal_anim")
        self.canvas.create_text(
            cx, cy, text="+", fill=green, font=("Arial", 14, "bold"), tags="heal_anim"
        )
        self.root.after(
            self._anim_delay(40), lambda: self._animate_heal(pos, on_done, frame + 1)
        )

    def _animate_small_arrow(self, pos, color, direction, tag, on_done, frame=0):
        """Animate a small arrow (up or down) at the given hex position.
        direction: -1 for up, +1 for down."""
        total_frames = 8
        if frame > total_frames:
            self.canvas.delete(tag)
            on_done()
            return
        t = frame / total_frames
        cx = self._hex_x(pos[0], pos[1])
        cy = self._hex_y(pos[0], pos[1]) + direction * t * 10
        alpha_frac = 1 - t
        self.canvas.delete(tag)
        # Arrow shaft
        y1 = cy - 6 * direction
        self.canvas.create_line(cx, cy, cx, y1, fill=color, width=2, tags=tag)
        # Arrowhead
        self.canvas.create_polygon(
            cx,
            y1,
            cx - 4,
            y1 + 5 * direction,
            cx + 4,
            y1 + 5 * direction,
            fill=color,
            tags=tag,
        )
        # Fade text label
        r_val = int(int(color[1:3], 16) * alpha_frac)
        g_val = int(int(color[3:5], 16) * alpha_frac)
        b_val = int(int(color[5:7], 16) * alpha_frac)
        faded = f"#{r_val:02x}{g_val:02x}{b_val:02x}"
        self.canvas.create_line(cx, cy, cx, y1, fill=faded, width=2, tags=tag)
        self.root.after(
            self._anim_delay(30),
            lambda: self._animate_small_arrow(
                pos, color, direction, tag, on_done, frame + 1
            ),
        )

    def _animate_splash_hit(self, pos, on_done, frame=0):
        """Animate a small red burst at the given position."""
        total_frames = 6
        if frame > total_frames:
            self.canvas.delete("splash_anim")
            on_done()
            return
        t = frame / total_frames
        cx = self._hex_x(pos[0], pos[1])
        cy = self._hex_y(pos[0], pos[1])
        self.canvas.delete("splash_anim")
        r = self.HEX_SIZE * 0.3 * (0.5 + t * 0.5)
        fade = int(255 * (1 - t))
        color = f"#ff{fade // 4:02x}{fade // 4:02x}"
        # Small expanding X
        for angle_deg in (45, 135):
            angle = math.radians(angle_deg)
            x1 = cx + r * math.cos(angle)
            y1 = cy + r * math.sin(angle)
            x2 = cx - r * math.cos(angle)
            y2 = cy - r * math.sin(angle)
            self.canvas.create_line(
                x1, y1, x2, y2, fill=color, width=2, tags="splash_anim"
            )
        self.root.after(
            self._anim_delay(35),
            lambda: self._animate_splash_hit(pos, on_done, frame + 1),
        )

    def _animate_sunder_arrow(self, target_pos, source_pos, on_done, frame=0):
        """Animate a small black down-arrow shifted toward source."""
        total_frames = 8
        if frame > total_frames:
            self.canvas.delete("sunder_anim")
            on_done()
            return
        t = frame / total_frames
        tx = self._hex_x(target_pos[0], target_pos[1])
        ty = self._hex_y(target_pos[0], target_pos[1])
        sx = self._hex_x(source_pos[0], source_pos[1])
        sy = self._hex_y(source_pos[0], source_pos[1])
        # Shift 30% toward source
        cx = tx + (sx - tx) * 0.3
        cy = ty + (sy - ty) * 0.3 + t * 8
        self.canvas.delete("sunder_anim")
        fade = int(200 * (1 - t))
        color = f"#{fade // 3:02x}{fade // 3:02x}{fade // 3:02x}"
        # Down arrow
        self.canvas.create_line(
            cx, cy - 8, cx, cy, fill=color, width=2, tags="sunder_anim"
        )
        self.canvas.create_polygon(
            cx, cy + 2, cx - 4, cy - 3, cx + 4, cy - 3, fill=color, tags="sunder_anim"
        )
        self.root.after(
            self._anim_delay(30),
            lambda: self._animate_sunder_arrow(
                target_pos, source_pos, on_done, frame + 1
            ),
        )

    def _animate_bombardment_arrow(self, src, dst, on_done, frame=0):
        """Animate a differently-colored arrow (orange) from src to dst."""
        total_frames = 8
        if frame > total_frames:
            self.canvas.delete("bomb_anim")
            on_done()
            return
        t = frame / total_frames
        sx, sy = self._hex_x(src[0], src[1]), self._hex_y(src[0], src[1])
        dx, dy = self._hex_x(dst[0], dst[1]), self._hex_y(dst[0], dst[1])
        cx = sx + (dx - sx) * t
        cy = sy + (dy - sy) * t
        self.canvas.delete("bomb_anim")
        angle = math.atan2(dy - sy, dx - sx)
        tail_x = cx - 10 * math.cos(angle)
        tail_y = cy - 10 * math.sin(angle)
        self.canvas.create_line(
            tail_x, tail_y, cx, cy, fill="#ff8800", width=2, tags="bomb_anim"
        )
        ha1 = angle + math.radians(150)
        ha2 = angle - math.radians(150)
        self.canvas.create_polygon(
            cx,
            cy,
            cx + 6 * math.cos(ha1),
            cy + 6 * math.sin(ha1),
            cx + 6 * math.cos(ha2),
            cy + 6 * math.sin(ha2),
            fill="#ff8800",
            tags="bomb_anim",
        )
        self.root.after(
            self._anim_delay(30),
            lambda: self._animate_bombardment_arrow(src, dst, on_done, frame + 1),
        )

    def _animate_stat_arrow(
        self, pos, color, direction, tag, on_done, source_pos=None, frame=0
    ):
        """Animate a small colored arrow at pos, optionally shifted toward source_pos.
        direction: -1 for up (buff), +1 for down (debuff)."""
        total_frames = 8
        if frame > total_frames:
            self.canvas.delete(tag)
            on_done()
            return
        t = frame / total_frames
        px = self._hex_x(pos[0], pos[1])
        py = self._hex_y(pos[0], pos[1])
        if source_pos:
            sx = self._hex_x(source_pos[0], source_pos[1])
            sy = self._hex_y(source_pos[0], source_pos[1])
            px = px + (sx - px) * 0.3
            py = py + (sy - py) * 0.3
        cy = py + direction * t * 10
        self.canvas.delete(tag)
        # Arrow shaft + head
        y_tip = cy + direction * (-8)
        fade = 1 - t
        r_c = int(int(color[1:3], 16) * fade)
        g_c = int(int(color[3:5], 16) * fade)
        b_c = int(int(color[5:7], 16) * fade)
        faded = f"#{max(0, r_c):02x}{max(0, g_c):02x}{max(0, b_c):02x}"
        self.canvas.create_line(px, cy, px, y_tip, fill=faded, width=2, tags=tag)
        self.canvas.create_polygon(
            px,
            y_tip + (-3 if direction == -1 else 3) * (-1),
            px - 4,
            y_tip + 5 * (-direction),
            px + 4,
            y_tip + 5 * (-direction),
            fill=faded,
            tags=tag,
        )
        self.root.after(
            self._anim_delay(30),
            lambda: self._animate_stat_arrow(
                pos, color, direction, tag, on_done, source_pos, frame + 1
            ),
        )

    def _chain_anims(self, anim_fns, final_done):
        """Run a list of animation functions in sequence. Each fn takes on_done callback."""
        if not anim_fns:
            final_done()
            return
        first = anim_fns[0]
        rest = anim_fns[1:]
        first(lambda: self._chain_anims(rest, final_done))

    def _make_sunder_anim(self, event):
        pos = event["pos"]
        src = event.get("source_pos")

        def anim(done):
            self._animate_stat_arrow(
                pos,
                "#444444",
                1,
                "sunder_anim",
                lambda: self._apply_event(event, done),
                source_pos=src,
            )

        return anim

    def _make_stat_arrow_anim(self, pos, color, direction, tag):
        def anim(done):
            self._animate_stat_arrow(pos, color, direction, tag, done)

        return anim

    def _make_splash_anim(self, event):
        pos = event["pos"]

        def anim(done):
            self._animate_splash_hit(pos, lambda: self._apply_event(event, done))

        return anim

    def _make_bombardment_anim(self, event):
        src = event.get("source_pos")
        dst = event["pos"]

        def anim(done):
            self._animate_bombardment_arrow(
                src, dst, lambda: self._apply_event(event, done)
            )

        return anim

    def _play_ability_anims(self, action, on_done):
        """Play visual effects for all abilities that triggered this step."""
        if not action:
            on_done()
            return
        anims = []

        for event in action.get("sunder_events", []):
            anims.append(self._make_sunder_anim(event))

        if action.get("ramp_pos"):
            anims.append(
                self._make_stat_arrow_anim(
                    action["ramp_pos"], "#ff4444", -1, "ramp_anim"
                )
            )

        for rpos in action.get("rage_positions", []):
            anims.append(self._make_stat_arrow_anim(rpos, "#ff6644", -1, "rage_anim"))

        for vpos in action.get("vengeance_positions", []):
            anims.append(self._make_stat_arrow_anim(vpos, "#ff2222", -1, "veng_anim"))

        for event in action.get("splash_events", []):
            anims.append(self._make_splash_anim(event))

        for event in action.get("bombardment_events", []):
            anims.append(self._make_bombardment_anim(event))

        for event in action.get("strike_events", []):
            anims.append(self._make_bombardment_anim(event))

        self._chain_anims(anims, on_done)

    def _play_attack_anim(self, action, on_done):
        """Play the appropriate animation for an attack action, then call on_done."""
        attacker_pos = action.get("attacker_pos", action.get("to"))
        if action["ranged"]:
            self._animate_arrow(attacker_pos, action["target_pos"], on_done)
        else:
            self._animate_slash(action["target_pos"], attacker_pos, on_done)

    def _play_heal_if_needed(self, action, on_done):
        """Play heal animations and apply their effects in sequence."""
        events = []
        if action:
            events.extend(action.get("heal_events", []))
            events.extend(action.get("fortify_events", []))
        if not events:
            on_done()
            return
        anims = []
        for event in events:
            pos = event["pos"]
            anims.append(
                lambda done, p=pos, e=event: self._animate_heal(
                    p, lambda: self._apply_event(e, done)
                )
            )
        self._chain_anims(anims, on_done)

    def _apply_event(self, event, on_done):
        self.battle.apply_effect_event(event)
        event["_applied"] = True
        self._draw()
        on_done()

    def _play_post_attack_anims(self, action, on_done):
        """Chain: heal -> ability effects."""

        def finalize():
            self._apply_all_events(action)
            self._draw()
            on_done()

        self._play_heal_if_needed(
            action, lambda: self._play_ability_anims(action, finalize)
        )

    def on_step(self):
        self.battle.step()
        action = self.battle.last_action
        self._draw()
        if action and action.get("type") in ("attack", "move_attack"):
            self._play_attack_anim(
                action, lambda: self._play_post_attack_anims(action, lambda: None)
            )
        else:
            self._play_post_attack_anims(action, lambda: None)

    def on_undo(self):
        self.battle.undo()
        self._draw()

    def on_reset(self):
        self.auto_running = False
        self.auto_btn.config(text="Auto")
        if self.return_btn:
            self.return_btn.destroy()
            self.return_btn = None
        self.battle = Battle(
            p1_units=self.battle._init_p1_units,
            p2_units=self.battle._init_p2_units,
            rng_seed=self.battle.rng_seed,
        )
        self.battle.apply_events_immediately = False
        self._draw()

    def _speed_down(self):
        if self.speed_index > 0:
            self.speed_index -= 1
            self.auto_delay = self.speed_levels[self.speed_index][0]
            self.speed_var.set(self.speed_levels[self.speed_index][1])

    def _speed_up(self):
        if self.speed_index < len(self.speed_levels) - 1:
            self.speed_index += 1
            self.auto_delay = self.speed_levels[self.speed_index][0]
            self.speed_var.set(self.speed_levels[self.speed_index][1])

    def on_skip(self):
        self.auto_running = False
        self.auto_btn.config(text="Auto")
        while self.battle.step():
            self._apply_all_events(self.battle.last_action)
        self._draw()

    def _apply_all_events(self, action):
        self.battle.apply_all_events(action)

    def toggle_auto(self):
        self.auto_running = not self.auto_running
        self.auto_btn.config(text="Stop" if self.auto_running else "Auto")
        if self.auto_running:
            self._auto_step()

    def _auto_step(self):
        if not self.auto_running:
            return
        cont = self.battle.step()
        self._draw()
        action = self.battle.last_action

        def schedule_next():
            if cont:
                self.root.after(self.auto_delay, self._auto_step)
            else:
                self.auto_running = False
                self.auto_btn.config(text="Auto")

        if action and action.get("type") in ("attack", "move_attack"):
            self._play_attack_anim(
                action, lambda: self._play_post_attack_anims(action, schedule_next)
            )
        else:
            self._play_post_attack_anims(action, schedule_next)


def main():
    root = tk.Tk()
    CombatGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
