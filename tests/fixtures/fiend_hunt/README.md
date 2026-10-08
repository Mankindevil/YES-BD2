# 魔兽追踪者 planning-screen fixtures

4K captures from the 4K PC (2026-09-30, 模擬戰鬥 Lv25) scaled to 1920×1080.
Only the regions the readers look at are kept (name/TEAM label, left list,
TURN/BATTLE pill, top-down grid and the floor under it, BATTLE END, the
更换队伍 dialog title); every other pixel is black. Made by a one-off script
from the explore frames.

| file | screen |
| --- | --- |
| `planning_topdown_t1.png` | TURN 1, TEAM1, top-down view, nobody selected |
| `real_cave_isometric_t1.png` | real fight (cave backdrop), TURN 1, isometric view, auto skills on |
| `real_cave_topdown_t1.png` | the same fight top-down: purple-tinted grid floor, grey 98 |
| `held_cell_slot4.png` | after holding cell (row 2, col 2): list slot 4 (杰尼斯) selected, name top-left |
| `team2_planning_t13.png` | TURN 13, TEAM2 (switched by the game), 6 slots incl. the summon, isometric |
| `team2_summon_selected.png` | TEAM2 with slot 6 selected: 魔法增幅器ET001 and its skill cards |
| `out_slots_t11.png` | TURN 11 with list slots 3-5 dead (OUT) |
| `battle_end.png` | BATTLE END screen |
| `change_team_dialog.png` | 更换队伍 confirmation dialog over the planning screen |

Card-column fixtures (2026-10-01, same fight; only the selection brackets and
the card column right of the list are kept):

| file | screen |
| --- | --- |
| `cards_t1_attack_lit.png` | TURN 1 top-down, 克蕾西亚 selected, 最前方 (attack) lit, 3 skill cards |
| `cards_t1_skill_lit.png` | TURN 1, 马莫尼勒 selected, her 2nd skill card lit |
| `cards_t1_knockback_lit.png` | TURN 1, 班塔纳 selected, 击退 lit |
| `cards_t13_four_skills.png` | TURN 13 isometric, 鲁 selected: 4 skill cards, attack lit |
| `cards_t13_summon.png` | TURN 13, 魔法增幅器ET001 selected, its one skill card lit |
| `cards_t13_preempt_on.png` | TURN 13, 格兰希特 with both 先发制人 switches on (skill cards greyed) |
| `cards_t13_none.png` | TURN 13, nobody selected: no card column |
| `cards_t21_bright_skill_art.png` | TURN 21 top-down, 帕莱特 on 越过 (attack), bright purple skill art, 2nd skill greyed (cooldown) |

List-entry fixtures for `same_card` (2026-10-01, same fight; only the left
list is kept, x 0-270 / y 100-650 at 1080p). "Settled" = captured after the
glow that sweeps an entry for ~0.1 s after a pick or a tap on ⇅ has passed.
Made by `.local-dev/fiend_hunt/make_list_fixtures.py` on the 4K PC.

| file | screen |
| --- | --- |
| `list_t1_start.png` | TURN 1, settled: 克蕾西亚 attack, 马莫尼勒 技能2, the rest attack |
| `list_t1_slot2_skill1.png` | as start, 马莫尼勒 on 技能1 (settled) |
| `list_t1_slot2_skill1_arc.png` | the same, right after the pick: the arc sweeps slot 2 |
| `list_t1_slot1_skill2.png` | as start, 克蕾西亚 on 技能2 (settled) |
| `list_t13_start.png` | TURN 13 (TEAM2, 6 slots), summon on its skill |
| `list_t13_summon_attack.png` | as T13 start, the summon (slot 6) on attack |
| `list_t11_saved_arc.png` | self_1001b's saved T11 screenshot: arc over 班塔纳 (slot 5) |
| `list_t11_live.png` | T11 of a replay of self_1001b with the same cards, settled |

Header fixture (2K PC, 2026-10-01, practice fight; only BURST_BOX is kept, scaled to 1080p):

| file | screen |
| --- | --- |
| `burst_header_t11_l2.png` | TURN 11, 克蕾西亚 selected on her skill card, header "◆5 ◷3 预约 BURST 2" |

List fixtures with 爆发 flames (2K PC, 2026-10-01, self_2k_b's saved screenshots; only the left list is kept, x 0-270 / y 100-650 at 1080p):

| file | screen |
| --- | --- |
| `list_2k_t01_bursts.png` | TURN 1: 马莫尼勒 (slot 2) BURST 3, the rest on attack |
| `list_2k_t07_bursts.png` | TURN 7: 克蕾西亚 (slot 1) BURST 2 |
| `list_2k_t23_bursts.png` | TURN 23 (TEAM2): 帕莱特 BURST 1, 海伦娜 BURST 3, other skills without a burst |
| `list_2k_t17.png` | TURN 17 (TEAM2): 帕莱特 (slot 1) on 恐惧之梦's skill |
| `list_2k_two_units_lower.png` | Leo's 2K PC 2026-10-07, TURN 1 top-down, a 2-unit team: the list sits ~10 px lower than usual, slot 2 selected (its card column open) |
| `cards_2k_t19_palette.png` | TURN 19 of a replay, 帕莱特 selected: list and card column (技能1 恐惧之梦 on cooldown, 技能2 奇迹紫罗兰 lit) |

Auto-skill icon (2K PC, 2026-10-01; only AUTO_SKILL_BOX is kept, scaled to 1080p):

| file | screen |
| --- | --- |
| `auto_skill_on.png` | TURN 1, the diamond (4th icon from the right) blue: auto skills on |
| `auto_skill_off.png` | the same after one tap: white, off (every unit on attack) |
| `auto_skill_spin_on_a.png`, `_b.png` | TURN 1, on: two captures ~0.09 s apart, the ⟳ turned between them (06:23 practice fight) |
| `auto_skill_spin_off_a.png`, `_b.png` | the same, off: two captures 0.1 s apart, nothing moved |

Screenshot-only fighting (`shots.py`; 2K PC, 2026-10-01, the same practice
fight recorded twice as self_2k_a and self_2k_b, everyone on the same cells;
scaled to 1080p, only the list, TEAM label, grid with the sprites above it,
floor and TURN/BATTLE kept):

| file | screen |
| --- | --- |
| `shots_2k_a_t07.png`, `shots_2k_b_t07.png` | TURN 7, TEAM1, 5 units, top-down, nobody selected (run a = live, run b = screenshot) |
| `shots_2k_a_t15.png`, `shots_2k_b_t15.png` | TURN 15, TEAM2 with the summon, 6 units |

Costume fixtures (4K PC, Leo 2026-10-06, a real fight's TURN 1, 艾尼尔 selected; scaled to 1080p, only the header x 500-1500 / y 0-160 and the list with the card column x 0-500 / y 0-650 kept):

| file | screen |
| --- | --- |
| `cards_4k_eleaneer_attack_lit.png` | 最前方 lit; skill cards 贯穿的魔弓, B级偶像, 夜色流影兔女郎 |
| `cards_4k_eleaneer_skill1_lit.png` | 技能1 lit: header "特级三重箭矢 +5" (souseha: 三重箭矢), the lit card's art changes expression |
