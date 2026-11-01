# Torroba: tempo 96–140, Juglar nghe được, và micro-shaping kiểu Barrios

> **Trạng thái**: kế hoạch, **chưa vào code**.
> **Sửa**: bảng BPM ở [`docs/sonify-guitar-torroba-aba-tempo.md`](./sonify-guitar-torroba-aba-tempo.md) mục 3 và mục 4, hàng `3/4, 60–72 BPM` ở [`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md) mục 2, và câu “hai cú sau thấp hơn một nấc `_under_lead`” trong cùng file mục 3.1.
> **Giữ**: không thêm id pattern. Không đổi id `torroba_tremolo`, tên in **Juglar**. Không đụng Barrios: `guitar.py` `_TREMOLO_THUMB` / `_tremolo` / `BARRIOS_TREMOLO_MIN_BPM` chỉ là tham chiếu, không sửa. Không sửa cờ `bridge` / `trio` trong `span.py`.

Bốn việc cùng một đợt: tempo mọi chương Torroba vào khoảng **96–140 BPM**; Juglar đạt **6,4–7,5 cú/giây** nên nghe ra tremolo; cú 2–4 của Juglar không còn rơi 14 bậc dưới cú 1; và cửa `bpm > 72` trong picker bị bỏ để chương chậm vẫn hát Juglar.

---

## 1. Việc đang nghe (rev 69)

Tremolo thật của guitar cổ điển là **6–12 cú/giây** (Barrios, Tárrega, Rodríguez). Juglar hôm nay hát **3 cú mỗi phách** (`_TRIPLET = 4/12`), nên số cú/giây chỉ bằng `bpm / 60 * 3`:

| BPM | Cú/giây hôm nay (3 cú/phách) | Nghe |
|---|---|---|
| 60 | 3,0 | nốt đen lặp, không phải tremolo |
| 66 | 3,3 | như trên |
| 72 | 3,6 | như trên |
| 90 | 4,5 | vẫn rời |
| 96 | 4,8 | vẫn rời |
| 108 | 5,4 | gần ngưỡng |
| 120 | 6,0 | tremolo, chỉ có ở 6/8 |

Chương 3/4 chậm nhất của bộ là **3M II ở 60 BPM** và chương chủ lực **1M II ở 72 BPM** — cả hai đều dưới ngưỡng. Đây là lý do Juglar không nghe ra tremolo, không phải vì accent hay vì sóng.

Cùng lúc, biên độ giữa cú 1 và cú 2–3 quá lớn. `tmp/diag_torroba_tempo.py`, 3/4, 96 BPM, rally, 8 ô, band `mf`:

| Tầng | Cú 1 phách 0 | Cú 2 | Cú 3 | Chênh |
|---|---|---|---|---|
| Trước sóng (viết) | 70 | 56 | 56 | 14 / 14 |
| Sau sóng (nghe) | 53 | 39 | 39 | 14 / 14 |
| Barrios `p-a-m-i`, cùng band | 52 | 55 | 54 | cú 2–3 **cao hơn** cú 1 |

Cú 2–3 chỉ còn **74%** biên độ cú 1 (−2,6 dB). Nghe thành “một nốt rồi hai tiếng đệm”, đúng như báo cáo. Gốc: `_render_juglar_bar` gọi `_one_under(velocity, band)`, một hàm **cố định** trả `_BAND_SUPPORT[band] - 2` (56 ở `mf`), không đọc `velocity`. Cú 1 thì đi qua `_lead_vel` rồi `_three_four_offbeat` rồi `apply_torroba_sung_arch` (+6/+4/0), nên hai đầu càng xa nhau ở phách 0.

Barrios không làm vậy. `guitar.py` `_tremolo` giữ **cùng một `_TREMOLO_THUMB`**, và `_one_under`/`_BAND_SUPPORT` chỉ dùng cho bè đệm; bốn cú lấy `velocity` từ một đường duy nhất rồi `apply_guitar_wave` cộng **một lượng affine cho cả ô**, nên khoảng trong cụm giữ nguyên sau sóng. Đó là mô hình để chép.

---

## 2. Luật tempo

Ba hằng số mới trong `guitar_torroba.py`:

```python
TORROBA_TEMPO_MIN = 96
TORROBA_TEMPO_MAX = 140
TORROBA_TEMPO_FLOOR = {
    ("calm", "3/4"): 96,
    ("calm", "4/4"): 96,
    ("calm", "6/8"): 104,
    ("selloff", "3/4"): 104,
    ("selloff", "4/4"): 104,
    ("selloff", "6/8"): 116,
    ("rally", "3/4"): 112,
    ("rally", "4/4"): 120,
    ("rally", "6/8"): 120,
    ("volatile", "3/4"): 124,
    ("volatile", "4/4"): 132,
    ("volatile", "6/8"): 140,
}
```

`retarget_torroba_tempo(spec, character)` trong `span.py`, cạnh `retarget_torroba_meter` (dòng 290), **chỉ nâng, không hạ** — trừ khi một spec đã vượt trần, khi đó `min` kéo nó về 140; hôm nay cao nhất là 124 nên nhánh đó không chạy.

```python
def retarget_torroba_tempo(spec: FormSpec, character: MovementCharacter | None) -> FormSpec:
    """Lift a Torroba movement into 96–140 BPM. Nothing slower than 96 survives."""
    kind = f"{spec.meter.beats}/{spec.meter.beat_type}"
    floor = TORROBA_TEMPO_FLOOR.get((character or "calm", kind), TORROBA_TEMPO_MIN)
    bpm = min(TORROBA_TEMPO_MAX, max(spec.bpm, floor))
    if bpm == spec.bpm:
        return spec
    return replace(spec, bpm=bpm)
```

Mood lạ (`None`) lấy hàng `calm`. Nhịp lạ lấy `TORROBA_TEMPO_MIN`. Gọi **ngay sau** `retarget_torroba_meter`, vì nhịp đổi trước rồi floor đọc nhịp mới. Bốn chỗ gọi, cùng mood mà cửa nhịp đang dùng:

| Chỗ | Dòng | Câu |
|---|---|---|
| `_framed_torroba` (1M, 3M) | 307 | `attach_frame(retarget_torroba_tempo(retarget_torroba_meter(body, character), character), span)` |
| `prepare_week` (1W) | 1113 | `spec = retarget_torroba_tempo(retarget_torroba_meter(spec, session_characters[0]), session_characters[0])` |
| `prepare_year` (1Y) | 1245 | `spec = attach_frame(retarget_torroba_tempo(retarget_torroba_meter(bodies[...], character), character), "1Y")` |
| 1D | — | không có spec, đi `GUITAR_BPM['torroba']` |

1W đọc mood của **phiên đầu** (`session_characters[0]`), giống hệt cửa nhịp ngay cạnh nó, không đọc mood của cả tuần. 1D vẫn 96 vì `GUITAR_BPM['torroba']` đã đúng sàn; muốn 1D theo mood thì phải thêm một bảng thứ hai ở `render.py` dòng 1281 — để sau, không thuộc đợt này.

`retarget_torroba_meter` giữ nguyên hợp đồng “tempo không đổi” — đó là lý do tách hàm mới thay vì nhét floor vào hàm cũ.

Kết quả trên các chương có thật:

| Nguồn | Nhịp | Mood | Hôm nay | Sau |
|---|---|---|---|---|
| 1W (tuần) | 3/4 | phiên đầu calm | 90 | **96** |
| 1W | 4/4 | phiên đầu rally | 90 | **120** |
| 1W | 3/4 | phiên đầu selloff | 90 | **104** |
| 1M I | 3/4 | calm | 96 | 96 |
| 1M I | 4/4 | rally | 96 | **120** |
| 1M II | 3/4 | calm | 72 | **96** |
| 1M III | 6/8 | selloff | 120 | 120 |
| 1M IV | 4/4 | rally | 96 | **120** |
| 3M II | 3/4 | calm | 60 | **96** |
| 3M II | 3/4 | rally | 60 | **112** |
| 3M III | 4/4 | volatile | 108 | **132** |
| 1Y mở | 4/4 | calm | 100 | 100 |
| 1Y giữa | 3/4 | calm | 66 | **96** |
| 1Y giữa | 3/4 | volatile | 66 | **124** |
| 1Y closer | 6/8 | rally | 108 | **120** |
| 1Y cuối | 4/4 | rally | 96 | **120** |
| 1D | 3/4 | calm | 96 | 96 |

Mọi giá trị rơi trong `[96, 140]` và **không chương nào chậm đi**. 1D không có `_spec`, đi `GUITAR_BPM['torroba'] = 96` (`guitar.py` dòng 24) — đã đúng sàn.

Thời lượng đổi theo: 1M II 160 ô 3/4 từ 400 giây xuống **300 giây**; 3M II từ 480 xuống **300**. Không test nào khóa độ dài file, nhưng WAV trong cache phải render lại — xem mục 7.


---

## 3. Bỏ cửa `bpm > 72` trong picker

Đây là chỗ dễ hỏng nhất. `_torroba_primary` (dòng 35) và `_torroba_contrast` (dòng 73) đang đọc `ctx.bpm`:

```python
if ctx.kind == "3/4" and mood not in {"rally", "selloff", "volatile"}:
    if ctx.bpm > 72:
        return "sonatina"
    return "castillo"
```

Nếu chỉ nâng tempo mà giữ cửa này thì **chương calm 3/4 mất Juglar**. Đo được, `tmp/diag_torroba_tempo.py`:

```
  60 BPM -> primary castillo   contrast torroba_tremolo
  72 BPM -> primary castillo   contrast torroba_tremolo
  96 BPM -> primary sonatina   contrast castillo
 104 BPM -> primary sonatina   contrast castillo
```

Tức 1M II ở 96 BPM sẽ thành `Sonatina — Castillo — Sonatina`, không còn cú tremolo nào trong chương. Cửa `> 72` là mẹo cũ để tránh tremolo ở tempo nhanh; mục 4 làm nó vô nghĩa vì mật độ cú tự đổi theo tempo. Bỏ cả hai cửa:

- `_torroba_primary`: 3/4 calm → **`castillo`** ở mọi tempo, tức khối dòng 47–50 rút còn `if ctx.kind == "3/4" and mood not in {"rally", "selloff", "volatile"}: return "castillo"`.
- `_torroba_contrast`: `castillo` trên 3/4 với mood calm → **`torroba_tremolo`** ở mọi tempo, tức dòng 90–94 rút còn `if mood == "calm": return "torroba_tremolo"`.

Docstring của hai hàm (dòng 41–42 và 80–82) đang viết “Sonatina above 72 and Castillo at 72 or below”, phải sửa theo, nếu không lần sau lại có người dựng lại cửa đó.

Sau đó bảng mood trong code khớp đúng bảng ở [`docs/sonify-guitar-torroba-aba-tempo.md`](./sonify-guitar-torroba-aba-tempo.md) mục 3–4, vốn đã ghi `3/4 calm → Castillo` và `Castillo — Juglar — Castillo` mà code chưa làm theo.

Cửa thứ ba, `_edge_frame` (dòng 4531), `if ctx.bpm <= 72 or (mood == "selloff" and ctx.kind == "6/8")`, cũng thành code chết vì sàn là 96. Sửa thành `if mood == "selloff" and ctx.kind == "6/8"`. Hệ quả: khung intro/outro của chương 3/4 `volatile` và `selloff` dùng cách búng nhanh (`_fandanguillo_melody` / nốt mạnh) thay vì nốt ngân 1 phách — đúng ở 104–124 BPM.


---

## 4. Mật độ cú của Juglar

`_render_juglar_bar` (dòng 3757) đang cứng 3 cú/phách. Cho nó đọc tempo:

```python
JUGLAR_TRIPLET_BPM = 120   # 120 BPM trở lên: bộ ba 3:2, đúng hình đã soạn
JUGLAR_FILL = {3: (0, -3, -4), 4: (0, -3, -4, -3)}
```

```python
def _juglar_attacks(ctx) -> int:
    """Four to the beat under 120 BPM, the written 3:2 triplet at or above it."""
    return 3 if ctx.bpm >= JUGLAR_TRIPLET_BPM else 4
```

Trong `_render_juglar_bar` (dòng 3757, sau khi đã có `quarter_notes`), `attacks`/`step` dùng chung cho cả `apply_torroba_sung_arch` ở mục 5.2:

```python
attacks = _juglar_attacks(ctx)
step = _TRIPLET if attacks == 3 else 0.25
```

Ba cú (0, 4/12, 8/12) đổi thành bốn cú (0; 0,25; 0,5; 0,75). Bốn móc kép trong một phách là lưới 16 → `divisions = 4` (`_needs_sixteenths`), còn ba cú vẫn đòi `divisions = 12` (`_needs_twelfths`) — cả hai đường đã có sẵn trong `render_patterned_voices` (`guitar_patterns.py` dòng 3601–3621), không phải sửa gì. Đo trên bản mô phỏng: 96 và 112 BPM ra `divisions=4`, 120 và 140 ra `divisions=12`, và `assert_playable(..., profiles="torroba")` qua ở cả năm tempo. Chương có Castillo làm khung thì `divisions` vẫn có thể ra 12 do rasgueado của Castillo; cụm 0,25 vẫn đứng đúng trên lưới 12 (0,25 × 12 = 3), nên không có gì phải ép.

Số cú/giây sau khi đổi:

| BPM | Cú/phách | Cú/giây | Chương |
|---|---|---|---|
| 96 | 4 | **6,4** | 1M II, 1Y giữa, 3M II (3/4 calm) |
| 104 | 4 | 6,9 | 3/4 selloff |
| 112 | 4 | **7,5** | 3/4 rally |
| 124 | 3 | 6,2 | 3/4 volatile (Juglar là contrast của Danza) |
| 120 | 3 | 6,0 | ngưỡng đổi hình; không chương 3/4 nào ở đúng 120 |
| 132 | 3 | 6,6 | 4/4 volatile, Juglar chỉ hát trên 3/4 |

Ngưỡng 120 chọn có chủ ý: giữ đúng hình **bộ ba 3:2** ở chương scherzo và ở 1M III (120 BPM) như [`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md) mục 3.1 đã khóa, và chỉ dùng móc kép 16 ở dải chậm, nơi bộ ba không đủ nhanh.

Ô cuối vùng Juglar (`_juglar_region_last`) vẫn một nốt mỗi phách, không phụ thuộc `attacks`.

---

## 5. Micro-shaping kiểu Barrios cho cụm Juglar

Hai thay đổi, cùng một mục đích: khoảng **bên trong** cụm là 3–4 bậc, không phải 14.

### 5.1 Cú 2–4 theo cú 1, không theo bảng

Trong `_render_juglar_bar`, thay

```python
dropped = _one_under(velocity, band)
lead.append(_heard(bar, beat, midi, _TRIPLET, 1, velocity, accent=accent))
lead.append(_heard(bar, beat + _TRIPLET, midi, _TRIPLET, 1, dropped))
lead.append(_heard(bar, beat + 2 * _TRIPLET, midi, _TRIPLET, 1, dropped))
```

bằng một vòng theo `JUGLAR_FILL`, dùng `attacks` và `step` của mục 4 (khi `quarter_notes` — `mode == "thin"` hoặc `_juglar_region_last` — thì vẫn một nốt mỗi phách như nhánh `continue` hiện tại):

```python
for index in range(attacks):
    offset = JUGLAR_FILL[attacks][index]
    lead.append(_heard(
        bar, beat + index * step, midi, step, 1,
        max(1, velocity + offset),
        accent=accent and index == 0,
    ))
```

`_one_under` và `_BAND_SUPPORT` không đổi — chúng còn dùng cho bè đệm và cho cửa intro/outro của Alcaniz/Olite/Castillo. Chỉ Juglar thân bài bỏ đường đó.

### 5.2 Vòng câu respell lại cả cụm, sau khi đã kẹp trần

`apply_torroba_sung_arch` (dòng 4480) chỉ nâng cú có `_sung_attack`, mà `_sung_attack` cho `torroba_tremolo` đòi `beat` là số nguyên. Bốn cú mới ở 0; 0,25; 0,5; 0,75 nên vẫn chỉ cú 1 lọt — đúng ý. Nhưng nếu chỉ nâng cú 1 thì phách 0 lại mở khoảng 6 bậc, phá 5.1.

Sửa: trong vòng câu, sau khi đã kẹp `applied` vào trần 72 cho cú 1, **respell lại các cú còn lại của cùng phách** thành `min(72, velocity_cú_1 + JUGLAR_FILL[attacks][i])`, cùng ô, cùng phách nguyên, cùng cao độ.

Thứ tự này quan trọng. Nếu cộng `applied` vào cụm *trước* rồi mới kẹp trần thì một cú 1 chạm 72 sẽ kéo cả cụm lên 72 và mất hẳn cái waver — đúng chỗ tremolo to nhất. Đo được khi mô phỏng sai thứ tự: ô 0 ra `[72, 72, 72, 72, ...]`. Đặt fill sau trần thì ô đó ra `[70, 67, 66, 67, ...]`.

`apply_guitar_wave` cộng một lượng affine cho cả ô, nên khoảng trong cụm sống sót tới tai người nghe.

Có lý do thứ hai để respell ở đây chứ không chỉ cộng dồn: `render_patterned_voices` chạy `_shape_dynamics` (dòng 3583) **trước** vòng câu. `_shape_dynamics` gán extra theo `eighth = floor(beat * 2)`, mà bốn cú trong cùng một phách rơi vào **hai** eighth khác nhau (0; 0,25 → eighth 0, còn 0,5; 0,75 → eighth 1). Câu nhạc có `rise > 0` thì extra hai bên lệch nhau 0–1 bậc, tức cái waver bị bẻ nhẹ. Respell trong vòng câu ghi đè luôn phần lệch đó, nên cụm ra đúng `cú 1 + fill` bất kể câu nhạc. Không phải sửa `guitar_patterns.py`.

Cài đặt gọn: `_bar_pattern` đã import sẵn trong hàm (dòng 4470), `JUGLAR_TRIPLET_BPM` và `JUGLAR_FILL` cùng module, nên `attacks` tính lại y hệt `_render_juglar_bar` mà không cần truyền gì thêm. Vòng quét anh em chỉ chạy khi pattern là `torroba_tremolo`, nên danza/castillo và cửa intro/outro không bị đụng.

Hàm phụ mới, đặt cạnh `apply_torroba_sung_arch`:

```python
def _juglar_cluster(events, sung: NoteEvent) -> list[int]:
    """Indexes of the attacks of `sung`'s beat, in attack order."""
    beat = int(sung.beat)
    found = [
        cursor for cursor, event in enumerate(events)
        if event.voice == 1 and event.bar == sung.bar and event.midi == sung.midi
        and beat <= event.beat < beat + 1
    ]
    return sorted(found, key=lambda cursor: events[cursor].beat)


def _respell_juglar_cluster(ctx, events: list[NoteEvent], sung: NoteEvent) -> None:
    """Siblings follow the sung attack, 3–4 degrees apart, under the 72 cap.

    The fill lands after the cap, not before: an attack 1 that reaches 72 keeps
    its waver instead of flattening the whole beat.
    """
    attacks = _juglar_attacks(ctx)
    cluster = _juglar_cluster(events, sung)
    if len(cluster) != attacks:
        return
    base = int(events[cluster[0]].velocity or 0)
    for order, cursor in enumerate(cluster):
        events[cursor] = replace(
            events[cursor], velocity=max(1, min(72, base + JUGLAR_FILL[attacks][order]))
        )
```

Trong vòng câu, sửa khối ghi cuối cùng thành:

```python
        for (_onset, _bar, index), amount in zip(chosen, amounts):
            event = events[index]
            room = 72 - int(event.velocity or 0)
            applied = min(amount, room) if room > 0 else 0
            if applied > 0:
                event = replace(event, velocity=int(event.velocity) + applied)
                events[index] = event
            if _bar_pattern(ctx, event.bar, patterns) == "torroba_tremolo":
                _respell_juglar_cluster(ctx, events, event)
```

Respell chạy cả khi `applied == 0`: lúc đó `base` vẫn là velocity gốc nên cụm ra y hệt lúc render, nhưng nó xóa luôn phần lệch do `_shape_dynamics` để lại — cụm Juglar luôn là `cú 1 + fill`, không phụ thuộc câu nhạc đi qua hai bucket eighth.

`cluster[0]` luôn là cú 1 đã kẹp trần, vì mọi cú trong một phách Juglar dùng chung `midi` (một `_melody_at` cho cả bốn). Cụm một nốt — ô cuối vùng Juglar, `mode == "thin"` — có `len(cluster) == 1 != attacks` nên thoát sớm, đúng ý.

Kết quả, `tmp/diag_juglar_cluster_plan.py`, 3/4, 96 BPM, rally, `mf`, ô 0:

| Tầng | Phách 0 | Phách 1 | Phách 2 |
|---|---|---|---|
| Hôm nay (viết) | 70 / 56 / 56 | 66 / 56 / 56 | 62 / 56 / 56 |
| Sau 5.1 + 5.2 (viết) | 70 / 67 / 66 / 67 | 66 / 63 / 62 / 63 | 62 / 59 / 58 / 59 |
| Sau sóng (nghe) | 53 / 50 / 49 / 50 | 49 / 46 / 45 / 46 | 45 / 42 / 41 / 42 |

Cú 2 so với cú 1 còn **94%** thay vì 74%, và phách vẫn nhô lên theo vòng câu (53, 49, 45). Đây là hình Barrios (`52 / 55 / 54 / 52`) đảo dấu: Barrios nhấn cú 2, Torroba nhấn cú 1 vì phách, cả hai đều là *waver*, không phải hai tầng rời nhau.

Trần 72 không còn là vấn đề: cú 2–4 luôn thấp hơn cú 1 đã kẹp, nên `min(72, ...)` chỉ chạm ở cú 1 khi vòng câu muốn hơn 72.


---

## 6. Chữ ký Juglar + Danza

Hôm nay chương 3/4 **rally** hát `Juglar — Danza — Juglar`; chương **calm** chỉ hát `Castillo — Juglar — Castillo` khi tempo ≤ 72, còn ở 96 thì rơi `Sonatina — Castillo — Sonatina` (mục 3). Sau khi bỏ cửa đó, cả hai chương đều có Juglar. Nhưng `Juglar — Danza — Juglar` cho 1M II ở 96 BPM nghĩa là 5 phút gần như toàn tremolo (A chiếm hai slot, B chỉ 8–24 ô). Tai mỏi, và tremolo mất tính “bài ngắn”.

Chốt hai luật, kiểm được bằng test:

1. **Chương 3/4 có Juglar thì phải có Danza hoặc Castillo làm khung.** Cụ thể: `torroba_tremolo` không bao giờ là primary duy nhất của một chương 3/4 — rally có `danza` làm contrast, calm có `castillo` làm khung. Đây là chữ ký của Torroba so với Barrios: tremolo **luôn** nằm trong một chương có điệu, không đứng một mình.
2. **Vùng Juglar trong chương calm bị chặn độ dài.** Vùng B của 1M II là cả slot giữa (24 ô, ô 46 tới 69). Giữ 24 ô, nhưng 8 ô cuối của vùng B hát `danza` khi chương là calm, để câu “tremolo + điệu ngắn” có thật trong một chương; `pattern_form` in `Castillo — Juglar — Danza — Castillo`.

Luật 2 là phần **tùy chọn**. Nếu không muốn đụng `_assign_macro`, bỏ luật 2 và giữ `Castillo — Juglar — Castillo`; chữ ký khi đó chỉ còn ở mức cả bộ (luật 1). Khuyến nghị: làm luật 1 trước, nghe lại, rồi mới quyết luật 2.

Ba điều **không** làm:

- Không cho Juglar hát trên 4/4 hay 6/8. `_render_juglar_bar` rơi `_downbeat_only` ở đó, đúng như cũ.
- Không hạ tempo để tremolo “dày”: dưới 96 thì 4 cú/phách vẫn chỉ 6,4 cú/giây, hạ nữa là rời.
- Không đổi `_grid_state`. `full` / `thin` vẫn như cũ; `pushed` của Juglar đã bị bỏ từ trước.


---

## 7. File đổi, test đổi, revision

**Code**

| File | Đổi |
|---|---|
| `backend/app/sonify/guitar_torroba.py` | hằng số mới ở dòng ~32; `_torroba_primary` bỏ cửa `> 72`; `_torroba_contrast` bỏ cửa `> 72`; `_render_juglar_bar` hát `attacks` cú theo `JUGLAR_FILL`; `apply_torroba_sung_arch` respell cả cụm sau khi kẹp trần; `_edge_frame` bỏ `ctx.bpm <= 72` |
| `backend/app/sonify/span.py` | `retarget_torroba_tempo` mới cạnh dòng 290; gọi ở `_framed_torroba` (307), `prepare_week` (1113), `prepare_year` (1245) |
| `backend/app/sonify/audio.py` | `SPAN_REVISION` `"69"` → `"70"` (dòng 43) — WAV cũ phải render lại |
| `backend/tmp/diag_juglar_cluster_plan.py` | đã viết xong (chạy được, exit 0). Sau khi vào code thì bỏ hai dòng vá ở `main()` để nó đo code thật |

`guitar_patterns.py`, `guitar_wave.py`, `guitar.py`, `guitar_frame.py` **không sửa**. `GUITAR_BPM['torroba']` giữ 96.

**Test**

| File | Dòng | Đổi |
|---|---|---|
| `tests/test_sonify_guitar_torroba.py` | 2995–3003 | `fast_waltz` (96 BPM) giờ ra `castillo` / `torroba_tremolo` như `waltz` ở 72. Gộp hai khối, thêm test khóa “tempo không đổi picker” cho 60/72/96/120/140 |
| | 3130–3205 | `test_juglar_triplets_accent_only_the_downbeat` → `test_juglar_cluster_follows_the_beat`. Trong khối này: 3148 giữ `[0]` (bass không đổi); 3153 tick `[+0, +4, +8]` → `[+0, +3, +6, +9]`; 3155 `duration 0.25`; 3156 `attacks[1].velocity == attacks[2].velocity < attacks[0].velocity` → `attacks[0].velocity > attacks[1].velocity > attacks[2].velocity` và `attacks[2].velocity < attacks[3].velocity` (fill `(0, -3, -4, -3)`); 3158 `not attacks[1].accent and not attacks[2].accent` → `not any(note.accent for note in attacks[1:])`; 3160 giữ (cú 1 vẫn đúng `ordinary`); 3163 `round(beat * 12) % 4 == 0` → `round(beat * 4)`; 3174/3192/3199 `len(...) == 9` → `12`; 3176/3201 `duration 0.25`. Thêm case `bpm=120` vẫn 3 cú tick `[0, 4, 8]`, `duration 4/12`, `attacks[1] > attacks[2]` |
| | 3495–3503 | `juglar_lead`: 3500 `last.duration_beats` `4 / 12` → `0.25`. `last` là cú **đầu** của phách 2 nên `velocity` vẫn `max(40, owned - 2)` |
| | 3208–3209 | **giữ nguyên**: `_shape_dynamics` không sửa, nên gap 4 vẫn là 4. Đây là test của hàm, không phải của `JUGLAR_FILL` |
| | 3701–3738 | `test_juglar_bar_before_the_return_stays_triplets` → `..._stays_a_cluster`: 3734 `len(earlier) == 9` → `12`, 3735 `duration 0.25`; `last` (3737–3739) giữ 3 nốt đen, không đổi |
| | 4408–4438 | `test_juglar_flat_bar_steps_the_later_beats`: docstring 4409 bỏ chữ “triplets”; 4431 `len(attacks) == 3` → `4`; 4432–4433 velocity `(64, 61, 60, 61)` và `(62, 59, 58, 59)`; 4435–4437 nhánh `quarters` (nốt đen, ô cuối vùng) giữ nguyên `[64, 62, 62]` |
| `tests/test_span.py` | 344–358 | giữ nguyên (hàm nhịp vẫn “tempo không đổi”); thêm `test_torroba_tempo_floor_only_lifts` cho hàm mới: 60 → 96, 150 → 140, mood `None` → hàng `calm`, nhịp lạ → `TORROBA_TEMPO_MIN` |
| | 378–379 | `torroba[1].spec == attach_frame(retarget_torroba_tempo(bodies[1], "rally"), "1M")`, `bpm == 112` |
| | 382–383 | `torroba[3]` là rally 4/4 96 → 120: cả câu so sánh `attach_frame` lẫn `((4, 4), 120)` |
| | 406 | `quarter[0].spec.bpm == 104` (selloff 3/4) |
| | 409–411 | như dòng 378–379 với `"3M"`, `bpm == 112` |
| | 412–413 | `quarter[2]` volatile 4/4 108 → 132: cả câu so sánh lẫn `((4, 4), 132)` |
| | 430 | 100, giữ nguyên (calm 4/4 đã trên sàn) |
| | 433 | `year[1].spec == attach_frame(retarget_torroba_tempo(specs[1], "rally"), "1Y")` |
| | 435–436 | `year[2]` rally 4/4 96 → 120: cả câu so sánh lẫn `((4, 4), 120)` |
| | 450 | `opening_calm.spec.bpm == 96` (mood phiên đầu calm, nhịp 3/4). Test này đang khóa `90` |

`torroba[0]`, `torroba[2]` và `year[0]` đã ở hoặc trên sàn nên không đụng; `quarter[0]` chỉ đổi số `bpm`, câu `bars == bodies[0].bars + 12` vẫn đúng vì sàn không đổi số ô. Riêng `opening_rally` (dòng 456–460) mang character `selloff` nhưng sàn đọc mood **phiên đầu** là `rally` → 4/4 lên 120 thay vì 104; không test nào khóa số đó, và đây đúng là hành vi của cửa nhịp đang có.

`tests/test_sonify_guitar_torroba_doors.py` không đổi: fixture chỉ dùng `character="calm"` và `bpm=96`, không có `selloff`/`volatile`; cửa `_edge_frame` mà nó đi qua là mood calm nên không chạm nhánh `bpm <= 72`.

Ba nhóm **không** phải sửa, đã kiểm:

- Các test `divisions` (2645–2796) đều ép pattern `castillo` / `danza` / `fandanguillo` / `olite`, không có Juglar. Ở `bpm=120` trở lên Juglar vẫn `divisions = 12` như cũ.
- `assert_playable(score, profiles="torroba")` không có luật tốc độ cú, chỉ kiểm register / bàn tay / dây, nên 4 cú/phách (móc kép) qua bình thường.
- `_SUNG_ROWS`, `_CASTILLOS_WAVES` và profile sóng `("torroba", "torroba_tremolo")` (`guitar_wave.py` dòng 122) đọc theo `pattern` / `bar`, không theo số cú, nên không đụng.

---

## 8. Docs phải sửa

| File | Sửa |
|---|---|
| [`sonify-guitar-torroba-aba-tempo.md`](./sonify-guitar-torroba-aba-tempo.md) | Mục 1: `3/4, 72` → `3/4, 96`, `4/4, 96` → `4/4, 120`. Mục 3: ba bảng `90–108` / `60–72` / `108–120` → `108–140` / `96–124` / `108–140`. Mục 4 dòng 111 và 133: bỏ “Juglar đang thưa”. Dòng 149: bỏ câu “kiểu 7 và kiểu 8 chỉ mở khi BPM ≤ 72” (code đã không còn cửa đó). Dòng 157: `Castillo — Juglar — Castillo (3/4, 96 BPM)` |
| [`sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md) | Mục 2: hàng `3/4, 60–72 BPM` → `3/4, 96–124 BPM`. Mục 3.1: bốn cú, `JUGLAR_FILL`, `divisions = 4` ở dải chậm. Dòng 216: “móc 2 và móc 4 thấp hơn một nấc `_under_lead`” → “cú 2–4 theo `JUGLAR_FILL`” |
| [`sonify-guitar-torroba-dynamics.md`](./sonify-guitar-torroba-dynamics.md) | Dòng 99: vòng câu respell **cả cụm** Juglar theo cú 1 đã kẹp trần, không chỉ nâng cú 1 |
| File này | Trạng thái `đã vào code` sau khi xong, kèm số đo mới từ `tmp/diag_torroba_tempo.py` |

---

## 9. Cách kiểm

```bash
cd backend
python tmp/diag_juglar_cluster_plan.py     # cụm Juglar trước/sau sóng, có và không có fill
python tmp/diag_torroba_tempo.py          # bảng cú/giây + velocity trước/sau sóng
python tmp/diag_torroba_specs.py          # bpm từng chương sau retarget
python -m pytest tests/test_span.py tests/test_sonify_guitar_torroba.py \
                 tests/test_sonify_guitar_torroba_doors.py -q
python -m pytest tests/ -q -x             # SPAN_REVISION mới đụng test_ensemble
```

`tmp/diag_juglar_cluster_plan.py` vá `_render_juglar_bar` và `apply_torroba_sung_arch` ngay lúc chạy, không sửa file nào, nên dùng được cả trước khi vào code để chốt số. Sau khi vào code thì bỏ hai dòng vá ở `main()` là nó đo code thật.

Bốn con số phải đọc được ở đầu ra `diag_torroba_tempo.py`:

1. 3/4 calm 96 BPM → **6,4 cú/giây**, không còn 4,8.
2. Cụm ô 0 → `[70, 67, 66, 67]` trước sóng, `[53, 50, 49, 50]` sau sóng.
3. `calm 3/4 96 BPM -> primary castillo  contrast torroba_tremolo` (không còn `sonatina`).
4. Mọi `spec.bpm` trong `[96, 140]`, và không chương nào nhỏ hơn giá trị cũ.

`tmp/diag_juglar_cluster_plan.py` in thêm hai dòng đã đo được trên bản mô phỏng: `divisions=4` ở 96 và 112 BPM, `divisions=12` ở 120 và 140, và `assert_playable(score, profiles="torroba")` không ném ở cả năm tempo.

Rồi nghe lại 1M II và 3M II: tremolo phải thành một dải liền, không phải nốt đen có hai tiếng vọng.

---

## 10. Thứ tự làm

1. `span.py` + hằng số floor + `_framed_torroba`: tempo vào đúng dải. Chạy `tmp/diag_torroba_specs.py`, cập nhật `tests/test_span.py`.
2. Bỏ ba cửa `bpm` (`_torroba_primary`, `_torroba_contrast`, `_edge_frame`). Chạy lại diag: calm 3/4 phải ra `castillo` + `torroba_tremolo`. Cập nhật khối test 2995–3003.
3. `JUGLAR_FILL` + `attacks` trong `_render_juglar_bar`. Cập nhật các test mật độ.
4. `apply_torroba_sung_arch` respell cả cụm sau khi kẹp trần. Chạy `tmp/diag_juglar_cluster_plan.py`, đo lại `[70, 67, 66, 67]` trước sóng và `[53, 50, 49, 50]` sau sóng.
5. Bump `SPAN_REVISION` lên `"70"`, chạy cả bộ test.
6. Sửa ba file docs ở mục 8, đổi trạng thái file này.
7. Nghe 1M II, 3M II, 1M III. Quyết luật 2 của mục 6 sau khi nghe.

