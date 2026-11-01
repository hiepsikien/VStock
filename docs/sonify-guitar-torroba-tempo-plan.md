# Torroba: tempo 96–140, Juglar nghe được, và micro-shaping kiểu Barrios

> **Trạng thái**: **đã vào code**, `SPAN_REVISION` `"69"` → `"70"`, `pytest tests/ -q` **734 passed**. Đã kiểm bằng dữ liệu thật (112 mã × `1M`/`3M`/`1Y`): **169 chương 3/4 từ 112 BPM trở lên, cả 169 hát Juglar** — không chương nhanh nào rơi về `sonatina`. Chỉ còn bước nghe lại (mục 10, bước 8): `MSN 1M II` / `PVS 1M II` / `VCB 1M I`.
> **Sửa**: bảng BPM ở [`docs/sonify-guitar-torroba-aba-tempo.md`](./sonify-guitar-torroba-aba-tempo.md) mục 3 và mục 4, hàng `3/4, 60–72 BPM` ở [`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md) mục 2, và câu “hai cú sau thấp hơn một nấc `_under_lead`” trong cùng file mục 3.1.
> **Giữ**: không thêm id pattern. Không đổi id `torroba_tremolo`, tên in **Juglar**. Không đụng Barrios: `guitar.py` `_TREMOLO_THUMB` / `_tremolo` / `BARRIOS_TREMOLO_MIN_BPM` chỉ là tham chiếu, không sửa. Không sửa cờ `bridge` / `trio` trong `span.py`.

Đo lại sau khi vào code, `backend/tmp/diag_torroba_tempo.py`, 3/4 rally, 8 ô, band `mf`, **trước** sóng:

| BPM | Cú/giây (3 ngón + ngón cái) | Chùm một phách, viết | Ngón cái ba phách |
|---|---|---|---|
| 96 | 6,40 | `64 / 61 / 60` | `66 / 64 / 64` |
| 104 | 6,93 | như trên | như trên |
| 120 | 8,00 | như trên | như trên |
| 140 | 9,33 | như trên | như trên |

Chùm là hình **không phụ thuộc tempo**: cùng chín ngón và ba ngón cái ở mọi BPM. Khoảng bên trong chùm còn 3–4 bậc (trước là 14), ngón cái hát 2 bậc trên ngón to nhất của phách, và cú hát nằm ở `+0,25` phách. Ô cuối vùng vẫn một nốt mỗi phách (`64 / 62 / 62`, ba ngón nghỉ).

Bốn việc cùng một đợt: tempo mọi chương Torroba vào khoảng **96–140 BPM**; Juglar búng **bốn cú mỗi phách** (1 bass + 3 ngón) nên đạt **6,4–9,3 cú/giây** và nghe ra tremolo; ba ngón trong chùm chỉ còn cách nhau 3–4 bậc thay vì 14, và **ngón cái hát 2 bậc trên nốt to nhất của chùm** vì bass cũng là bè giai điệu; và cửa `bpm > 72` trong picker bị bỏ để chương chậm vẫn hát Juglar.

---

## 1. Việc đang nghe (rev 69)

Tremolo thật của guitar cổ điển là **6–12 cú/giây** (Barrios, Tárrega, Rodríguez). Juglar hôm nay hát **3 cú mỗi phách** (`_TRIPLET = 4/12`) và không búng bass lại, nên số cú/giây chỉ bằng `bpm / 60 * 3`:

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

`retarget_torroba_tempo(spec, character)` trong `span.py`, cạnh `retarget_torroba_meter` (dòng 290), **chỉ nâng, không hạ** — trừ khi một spec đã vượt trần, khi đó `min` kéo nó về 140; hôm nay cao nhất là **120** (1M III, 6/8) nên nhánh đó không chạy.

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
| `_framed_torroba` (1M, 3M) | 319 (hàm ở 307) | `attach_frame(retarget_torroba_tempo(retarget_torroba_meter(body, character), character), span)` |
| `prepare_week` (1W) | 1114 | `spec = retarget_torroba_tempo(retarget_torroba_meter(spec, session_characters[0]), session_characters[0])` |
| `prepare_year` (1Y) | 1237 | `spec = attach_frame(retarget_torroba_tempo(retarget_torroba_meter(bodies[...], character), character), "1Y")` |
| 1D | — | không có spec, đi `GUITAR_BPM['torroba']` |

1W đọc mood của **phiên đầu** (`session_characters[0]`), giống hệt cửa nhịp ngay cạnh nó, không đọc mood của cả tuần. 1D vẫn 96 vì `GUITAR_BPM['torroba']` đã đúng sàn; muốn 1D theo mood thì phải thêm một bảng thứ hai ở `render.py` dòng 1281 — để sau, không thuộc đợt này.

`retarget_torroba_meter` giữ nguyên hợp đồng “tempo không đổi” — đó là lý do tách hàm mới thay vì nhét floor vào hàm cũ.

Kết quả trên các chương có thật. Nhịp là nhịp **sau** `retarget_torroba_meter` —
đúng thứ tự gọi, nhịp đổi trước rồi floor đọc nhịp mới — nên 4/4 `calm`/`selloff`
thành 3/4 và 1M I, 3M I đọc hàng 3/4, không phải hàng 4/4:

| Nguồn | Nhịp | Mood | Hôm nay | Sau |
|---|---|---|---|---|
| 1W (tuần) | 3/4 | phiên đầu calm | 90 | **96** |
| 1W | 4/4 | phiên đầu rally | 90 | **120** |
| 1W | 3/4 | phiên đầu selloff | 90 | **104** |
| 1M I (96 ô) | 3/4 | selloff | 96 | **104** |
| 1M II (96 ô) | 3/4 | calm | 72 | **96** |
| 1M III | 6/8 | selloff | 120 | 120 |
| 1M IV | 4/4 | rally | 96 | **120** |
| 3M I | 3/4 | selloff | 96 | **104** |
| 3M II (160 ô) | 3/4 | calm | 60 | **96** |
| 3M II | 3/4 | rally | 60 | **112** |
| 3M III | 4/4 | volatile | 108 | **132** |
| 1Y mở | 3/4 | calm | 100 | 100 |
| 1Y giữa | 3/4 | calm | 66 | **96** |
| 1Y giữa | 3/4 | volatile | 66 | **124** |
| 1Y closer | 6/8 | rally | 108 | **120** |
| 1Y cuối | 4/4 | rally | 96 | **120** |
| 1D | 3/4 | calm | 96 | 96 |

Mọi giá trị rơi trong `[96, 140]` và **không chương nào chậm đi**; giá trị cao nhất
sau khi sửa là **132** (3M III, 4/4 `volatile`). 1D không có `_spec`, đi
`GUITAR_BPM['torroba'] = 96` (`guitar.py` dòng 24) — đã đúng sàn.

Thời lượng đổi theo, đo bằng `bars × beats / bpm`: 1M II **96 ô** 3/4 từ **240**
giây xuống **180**; 3M II **160 ô** 3/4 từ **480** xuống **300** (calm) hoặc
**257** (rally). Không test nào khóa độ dài file, nhưng WAV trong cache phải
render lại — xem mục 7.


---

## 3. Bỏ cửa `bpm > 72` trong picker

Đây là chỗ dễ hỏng nhất. `_torroba_primary` (dòng 48) và `_torroba_contrast` (dòng 91) đang đọc `ctx.bpm`:

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

Docstring của hai hàm (dòng 41–43 và 80–82) đang viết “Sonatina above 72 and Castillo at 72 or below”, phải sửa theo, nếu không lần sau lại có người dựng lại cửa đó.

Sau đó bảng mood trong code khớp đúng bảng ở [`docs/sonify-guitar-torroba-aba-tempo.md`](./sonify-guitar-torroba-aba-tempo.md) mục 3–4, vốn đã ghi `3/4 calm → Castillo` và `Castillo — Juglar — Castillo` mà code chưa làm theo.

Cửa thứ ba, `_edge_frame` (dòng 4531), `if ctx.bpm <= 72 or (mood == "selloff" and ctx.kind == "6/8")`, cũng thành code chết vì sàn là 96. Sửa thành `if mood == "selloff" and ctx.kind == "6/8"`.

**Thay đổi này không nghe thấy gì, và không nên đi tìm một thay đổi thính
giác.** Đo ba nhánh trước và sau khi bỏ `ctx.bpm <= 72`:

| mood | nhịp | hôm nay (`bpm <= 72`) | hôm nay (`bpm > 72`) | sau khi bỏ |
|---|---|---|---|---|
| selloff | 6/8 | nốt ngân | nốt ngân (nhánh 2) | nốt ngân |
| selloff | 3/4, 4/4 | nốt ngân | `_fandanguillo_melody` / nốt mạnh | y hôm nay |
| volatile | 3/4 | nốt ngân | `_fandanguillo_melody` | y hôm nay |

Sàn 96 (và 1D = `GUITAR_BPM['torroba'] = 96`) không còn để lại đường nào cho
`bpm <= 72` đi tới `_edge_frame`, nên đây thuần là **xóa code chết**: khung
intro/outro ở 104–124 BPM vốn đã đi nhánh nhanh từ trước.


---

## 4. Hình của Juglar: ba chùm bốn cú trên mỗi ô 3/4

Một ô 3/4 của Juglar là **ba chùm, mỗi chùm bốn cú** — đúng cách búng tremolo
p-a-m-i: ngón cái (bass) vào đầu phách, rồi ba ngón a-m-i bật cùng một nốt giá
đã quantize trên ba móc kép sau đó. Tổng 12 cú/ô: 3 bass + 9 nốt cao.

| Cú | Vị trí | Bè | Cao độ | Velocity |
|---|---|---|---|---|
| 1 | phách + 0 | 3 (bass) | `_sounding_bass`, búng lại mỗi phách, ngân 1 phách | `max(ba ngón của chùm) + 2`, sàn 42, trần 88 (5.1) |
| 2 | phách + 0,25 | 1 | `_melody_at` của eighth mở phách | `velocity + 0` |
| 3 | phách + 0,5 | 1 | y cú 2 | `velocity - 3` |
| 4 | phách + 0,75 | 1 | y cú 2 | `velocity - 4` |

Hai hệ quả, cả hai đều là điều mục 1 cần:

- **Bè cao đi đúng price action đã quantize.** Mỗi chùm lấy một `_melody_at`
  của eighth mở phách và lặp ba lần; không có cao độ mới, không quantize lại.
  `ctx.melody` đã là price đã quantize, `_melody_at` chỉ đọc nó, nên ba ngón
  trong chùm luôn cùng cao độ và cùng nằm trong scale/hợp âm như bản gốc.
- **Bass búng lại mỗi phách** thay vì ngân 1,5 phách như hiện tại. Cả ô thành
  một dòng 12 cú đều trên lưới móc kép, nên `divisions = 4`
  (`_needs_sixteenths`) tự ra, không phải sửa `render_patterned_voices`; đường
  `_needs_twelfths` không còn dùng cho Juglar.

Hằng số, thay chỗ `_TRIPLET` hiện tại:

```python
JUGLAR_FINGERS = (0, -3, -4)   # three fingers under the thumb pluck
JUGLAR_STEP = 0.25             # one sixteenth: four plucks per beat
JUGLAR_RISE = 2                # thumb 2 above the loudest finger of that beat, not of the bar
```

Trong `_render_juglar_bar` (dòng 3757), thay khối ba cú của mỗi phách bằng vòng
ba ngón **bắt đầu sau ngón cái một móc kép** — ngón cái đã nằm đúng trên phách,
nên phải là `index + 1`:

```python
for index, offset in enumerate(JUGLAR_FINGERS):
    lead.append(_heard(
        bar, beat + (index + 1) * JUGLAR_STEP, midi, JUGLAR_STEP, 1,
        max(40, velocity + offset),
        accent=accent and index == 0,
    ))
```

Viết `index` thay vì `index + 1` sẽ đặt ngón đầu **trùng** ngón cái ở `phách + 0`
và để trống móc `0,75`: vẫn 12 cú nhưng không đều, và cú hát lại rơi đúng trên
bass. Ba ngón vì thế nằm ở `phách + 0,25 / 0,5 / 0,75`, còn `phách + 0` là **của
riêng ngón cái**. Đúng vị trí đó là thứ mục 5.2 (`_first_of_beat`) và bảng test
ở mục 7 giả định.

rồi thêm một vòng thứ hai viết bass cho từng phách (khối bass hiện tại chỉ viết
một nốt ở eighth 0). Cao độ bass lấy **một lần cho cả ô**, từ bè hợp âm, rồi
**lặp lại** ở cả ba chùm:

- `_sounding_bass(ctx, bar, sung)` gọi **một lần**, với `sung = _melody_at(ctx, bar * ctx.epb)`.
  Gọi nó theo từng phách thì `_torroba_bass` loại bass khi `written >= lead`, mà
  câu đi lên/xuống hay `regime_at` đổi giữa ô có thể cho ra **ba dây buông khác
  nhau** — nghe thành một dòng bass bò, không phải ngón cái búng lại cùng một nốt.
- Nốt đó không đặt được ngón ở phách nào thì `_fitting_bass` tự thử **một** nốt
  bass khác của hợp âm (`_chord_bass_at`). Vì thế một ô có tối đa **hai** cao độ
  bass, cả hai đều là nốt của bè hợp âm — đúng luật “lặp lại, hoặc xoay trong 2
  nốt của bè hợp âm”, không bao giờ thành một dòng ba nốt khác nhau.
- Không xoay chủ động (bass → 5 → bass) trong đợt này: `_fitting_bass` đã thay
  thế khi cần, còn xoay tay thì phải tự kiểm `_bass_eighths_fit` cho từng phách.
  Nếu sau này muốn xoay thì vẫn chỉ dùng nốt của bè hợp âm, tối đa **3**.

Vòng thứ hai phải chạy **sau** vòng lead để `_fitting_bass` thấy được cả ba chùm,
và đọc lại `levels` mà vòng lead ghi (`velocity` đã qua `_three_four_offbeat`) chứ
không gọi lại `_lead_vel`. Nó chỉ dành cho nhánh tremolo — nhánh nốt đen
(`quarter_notes`) giữ nguyên khối cũ, kể cả thứ tự inner-trước-bass:

```python
levels: list[int] = []          # trong vòng lead: levels.append(velocity)
...
if quarter_notes:
    ...                         # khối 3785–3795 giữ nguyên: inner rồi _choose_bass_eighths
else:
    sung = _melody_at(ctx, bar * ctx.epb)
    bass = _sounding_bass(ctx, bar, sung)          # một lần cho cả ô
    if bass is not None:
        for quarter, (eighth, velocity) in enumerate(zip((0, 2, 4), levels)):
            bass_vel = _juglar_thumb([max(40, velocity + offset) for offset in JUGLAR_FINGERS])
            found = _fitting_bass(ctx, bar, eighth, bass, [*lead, *support], (2, 1))
            if found is None:
                continue
            pitch, length = found
            low.append(_heard(bar, float(quarter), pitch, length * 0.5, 3, bass_vel))
```

`if quarter_notes` không phải chi tiết vụn. Áp vòng bass mới cho **mọi** ô thì ô
cuối vùng (`_juglar_region_last`) và `mode == "thin"` mất `_choose_bass_eighths`
(bass 1,5 phách), mất nốt inner ở phách 1, và `test_juglar_bar_before_the_return_stays_triplets`
(3741) vỡ ở `len(last_low) == 1` / `1,5`. Hai nhánh đó **không phải tremolo**:
một nốt mỗi phách thì không có chùm để hát trên.

`support` trong nhánh tremolo là `[]` (nốt inner đã bỏ), nên `[*lead, *support]`
thực chất chỉ có lead; vẫn viết đủ hai danh sách để hợp đồng của `_fitting_bass`
(`company = [event for event in events if event.voice != 3]`) không đổi nếu sau
này inner quay lại.

`_fitting_bass` với `(2, 1)` ưu tiên bass ngân trọn phách, hạ xuống nửa phách
khi không đặt được ngón, và bỏ cú đó thay vì để `assert_playable` ném — đúng
hợp đồng sẵn có của hàm.

`bass_vel` lấy `max` của **đúng ba ngón trong phách đó**, không phải của cả ô —
nhờ vậy bass vẫn đi theo đường câu `72 / 68 / 64` thay vì phẳng `72 / 72 / 72`
(lý do ở mục 5.1). Lượt này cũng phải chạy lại sau arch, xem mục 5.3.

Số cú/giây sau khi đổi (4 cú/phách, gồm cả ngón cái):

| BPM | Cú/phách | Cú/giây | Chương |
|---|---|---|---|
| 96 | 4 | **6,4** | 1M II, 1Y giữa, 3M II (3/4 calm) |
| 104 | 4 | 6,9 | 3/4 selloff |
| 112 | 4 | **7,5** | 3/4 rally |
| 120 | 4 | 8,0 | sàn mới của 6/8 |
| 124 | 4 | 8,3 | 3/4 volatile (Juglar là contrast của Danza) |
| 140 | 4 | 9,3 | trần |

Cả dải nằm trong 6–12 cú/giây của tremolo thật, và mọi tempo đều dùng **cùng
một hình** — không còn ngưỡng đổi hình. Bộ ba 3:2 hiện tại
(`_TRIPLET = 4/12`) bị bỏ hẳn, kể cả ở 120 BPM trở lên: ba móc kép chồng ba
trên hai (3:2) không phải hình p-a-m-i, và ở 120 BPM nó chỉ cho 6,0 cú/giây
trong khi hình mới cho 8,0. Mục 3.1 của
[`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md)
đang khóa bộ ba 3:2, phải sửa theo mục này. 1M III ở 120 BPM là 6/8 nên đi
`_downbeat_only`, không đụng tới.

---

## 5. Micro-shaping kiểu Barrios cho cụm Juglar

Ba thay đổi, cùng một mục đích: khoảng **bên trong** chùm là 3–4 bậc (không phải
14), và **ngón cái là bè giai điệu thứ hai** nên nó hát trên cả chùm thay vì nằm
dưới.

### 5.1 Ba ngón theo phách, ngón cái hát trên chùm

Trong `_render_juglar_bar`, thay

```python
dropped = _one_under(velocity, band)
lead.append(_heard(bar, beat, midi, _TRIPLET, 1, velocity, accent=accent))
lead.append(_heard(bar, beat + _TRIPLET, midi, _TRIPLET, 1, dropped))
lead.append(_heard(bar, beat + 2 * _TRIPLET, midi, _TRIPLET, 1, dropped))
```

bằng vòng `JUGLAR_FINGERS` ở mục 4 cộng với luật cho ngón cái: **ngón cái là bè
giai điệu thứ hai, nên nó phải to hơn nốt to nhất của chùm 2 bậc**, không phải
nằm dưới như `_bed` vẫn làm.

```python
def _juglar_thumb(fingers: list[int]) -> int:
    """Ngón cái của chùm Juglar hát trên cả ba ngón: bass cũng là bè giai điệu."""
    return max(JUGLAR_THUMB_FLOOR, min(JUGLAR_THUMB_CEIL, max(fingers) + JUGLAR_RISE))
```

`JUGLAR_THUMB_FLOOR = 42`, `JUGLAR_THUMB_CEIL = 88`, `JUGLAR_RISE = 2`. Hai bậc
đúng bằng một `_MICRO` — bậc nhỏ nhất mà codebase đã dùng giữa hai bè — nên bass
nổi lên mà không thành một cú đập.

**Tham chiếu là `max` của đúng ba ngón trong phách đó**, không phải `max` của cả
ô. Chùm phách 0 to hơn hai chùm sau (`_three_four_offbeat` hạ dần), nên bass vẫn
đi theo đường của bè giá: `72 / 68 / 64` (viết) → `55 / 51 / 47` (nghe). Nếu lấy
`max` cả ô thì bass thành phẳng `72 / 72 / 72` (`55 / 55 / 55` sau sóng) — mất
đường đi, bass lại nghe như một cái pedal đệm chứ không phải bè giai điệu. Đây là
chỗ dễ “sửa nhầm” nhất trong hàm, nên `_juglar_thumb` chỉ nhận **một** tham số
`fingers: list[int]` (ba ngón của một phách) và chỗ gọi truyền đúng ba ngón đó.

Vì sao **không** dùng `_bed`: `_bed` → `_raised_bed` kẹp `bass = min(bass, lead - 2)`,
tức nó giả định bass là bè đệm dưới bè giá. Ở Juglar thì ngược lại — `_sounding_bass`
+ `_fitting_bass` viết cho ngón cái một **dòng bass riêng** (theo hợp âm và theo
cadence), nên nó là bè giai điệu thứ hai. Codebase đã có đúng thành ngữ này:
`tests/test_sonify_guitar.py::_assert_voices_separate(..., thumb=True)` đòi
`bass.velocity > lead.velocity` cho ô mà ngón cái mang giai điệu. Juglar giờ là
một trong số đó.

Bất biến của riêng chùm Juglar vì vậy là `bass > cú hát > ngón 2 > ngón 3`, không
còn `lead > bass`. Không chỗ nào cưỡng chế `lead > bass` bằng validate:
`assert_playable` chỉ kiểm register, thế tay và profile, không đọc velocity. Bè
inner cũng đã bỏ khỏi nhánh tremolo (dưới), nên không còn nốt đệm nào phải nằm
giữa bass và bè giá.

Đo trên bản mô phỏng (3/4, rally, mf, ô 0):

| Chùm | Trước wave (viết) | Sau wave (nghe) |
|---|---|---|
| phách 0 | `[70, 67, 66]`, ngón cái **72** | `[53, 50, 49]`, ngón cái **55** |
| phách 1 | `[66, 63, 62]`, ngón cái **68** | `[49, 46, 45]`, ngón cái **51** |
| phách 2 | `[62, 59, 58]`, ngón cái **64** | `[45, 42, 41]`, ngón cái **47** |

Cú 2 = **94%** cú 1 (trước đây cả ba cú đều `_one_under`, cú 2 chỉ còn 74%), hai
ngón sau cách ngón đầu 3–4 bậc, và ngón cái đúng +2 trên nốt to nhất của chùm ở
**cả hai** phía sóng: `apply_guitar_wave` là ánh xạ affine dùng chung một center
cho cả ô, nên `raw = C + (viết - 64)` giữ nguyên khoảng cách +2 (55 − 53, 51 − 49,
47 − 45). Dòng bass cũng đi theo vòng câu như bè giá (72 → 68 → 64), không phải
một mức phẳng.

`velocity` trong công thức phải là velocity **đã qua `_three_four_offbeat`** của
chính phách đó, không phải `_lead_vel` thô: phách 2 và 3 bị hạ 2 bậc. Vì vậy vòng
lead ghi lại `levels` theo phách, vòng bass đọc lại `levels` (xem mục 4) thay vì
gọi lại `_lead_vel`.

Luật này chỉ áp cho **chùm tremolo**. Nhánh nốt đen (`_juglar_region_last`,
`mode == "thin"`) không có chùm nào để hát trên, nên không đi qua `_juglar_thumb`:
bass vẫn `_bed` và vẫn nằm dưới bè giá như cũ, `_BAND_SUPPORT` và `_bed` không đổi.

`_one_under` thì **bị xóa**, cùng với `_TRIPLET`: dòng 3781 là chỗ gọi duy nhất
của `_one_under` (đã grep toàn repo) và `_TRIPLET` chỉ còn sống trong khối ba cú
vừa thay. Để lại một hàm không ai gọi là mời người sau dựng lại bộ ba 3:2.

Chùm tremolo **không có bè inner**: `_torroba_inner` bị bỏ khỏi nhánh tremolo,
vì chùm đúng bốn cú. Nốt inner đang viết ở phách 1 (dài nửa phách) của bản hiện
tại biến mất, cùng với chỗ tranh chấp giữa nốt đệm và ngón cái. Nhánh nốt đen
(ô cuối vùng, `mode == "thin"`) giữ nguyên bass + inner như cũ.

### 5.2 Vòng câu: chọn ngón đầu của chùm làm cú hát, rồi respell hai ngón sau

`apply_torroba_sung_arch` (dòng 4461) chỉ nâng cú mà `_sung_attack` nhận, và
`_sung_attack` cho `torroba_tremolo` đòi `beat` là **số nguyên** (dòng 4380–4381).
Bây giờ cú hát nằm ở `phách + 0,25`, nên luật đó không bắt được cú nào và cả
đoạn Juglar mất arch. Luật mới: cú hát là **cú lead sớm nhất của phách**.

```python
def _first_of_beat(events: list[NoteEvent]) -> dict[tuple[int, int], int]:
    """Index of the earliest lead attack in each bar beat."""
    first: dict[tuple[int, int], int] = {}
    for index, event in enumerate(events):
        if event.voice != 1 or event.midi is None or event.velocity is None:
            continue
        if event.velocity == 48:            # cùng luật 48 của _sung_attack
            continue
        key = (event.bar, int(event.beat))
        if key not in first or event.beat < events[first[key]].beat:
            first[key] = index
    return first
```

Điều kiện `velocity == 48` phải giữ: đó là mức đánh dấu “nốt lấy đà không hát”
mà `_sung_attack` (dòng 4378) đã dùng. Bỏ nó thì một cú móc kép 48 lọt vào đầu
phách sẽ cướp chỗ cú hát và chùm mất arch mà không ai thấy lỗi.

`first_of_beat` tính **một lần** cho cả lời gọi, ngay sau `events = list(lead)`
(dòng 4472), không tính lại trong vòng câu. Trong vòng, chỗ đang gọi
`_sung_attack(pattern, event)`:

```python
if pattern == "torroba_tremolo":
    sings = first_of_beat.get((event.bar, int(event.beat))) == index
else:
    sings = _sung_attack(pattern, event)
```

`_sung_attack` giữ nguyên cho danza/castillo/sonatina; chỉ nhánh tremolo không đi
qua nó nữa, nên dòng 4380–4381 thành code chết và bị xóa cùng docstring.

Sau đó, trong khối ghi cuối cùng của vòng câu, sau khi đã kẹp `applied` vào trần
72 cho cú hát, **respell hai ngón còn lại của cùng chùm** thành
`min(72, velocity_cú_hát + JUGLAR_FINGERS[i])`, cùng ô, cùng phách nguyên, cùng
cao độ.

Thứ tự này quan trọng. Nếu cộng `applied` vào cả chùm *trước* rồi mới kẹp trần
thì một cú hát chạm 72 sẽ kéo cả chùm lên 72 và mất hẳn cái waver — đúng chỗ
tremolo to nhất. Đặt fill sau trần thì chùm đó ra `[70, 67, 66]`.

`apply_guitar_wave` cộng một lượng affine cho cả ô, nên khoảng trong chùm sống
sót tới tai người nghe.

Có lý do thứ hai để respell ở đây chứ không chỉ cộng dồn: `render_patterned_voices`
chạy `_shape_dynamics` (dòng 4040) **trước** vòng câu. `_shape_dynamics` gán
extra theo `eighth = floor(beat * 2)`, mà ba ngón trong cùng một phách rơi vào
**hai** eighth khác nhau (0,25 → eighth 0; 0,5 và 0,75 → eighth 1). Câu nhạc có
`rise > 0` thì extra hai bên lệch nhau 0–1 bậc, tức cái waver bị bẻ nhẹ. Respell
trong vòng câu ghi đè luôn phần lệch đó, nên chùm ra đúng `cú hát + fill` bất kể
câu nhạc. Không phải sửa `guitar_patterns.py`.

Hàm phụ mới, đặt cạnh `apply_torroba_sung_arch`:

```python
def _juglar_cluster(events, sung: NoteEvent) -> list[int]:
    """Indexes of the fingers of `sung`'s beat, in attack order."""
    beat = int(sung.beat)
    found = [
        cursor for cursor, event in enumerate(events)
        if event.voice == 1 and event.bar == sung.bar and event.midi == sung.midi
        and beat <= event.beat < beat + 1
    ]
    return sorted(found, key=lambda cursor: events[cursor].beat)


def _respell_juglar_cluster(events: list[NoteEvent], sung: NoteEvent) -> None:
    """Fingers follow the sung finger, 3–4 degrees apart, under the 72 cap.

    The fill lands after the cap, not before: a sung finger that reaches 72 keeps
    its waver instead of flattening the whole beat.
    """
    cluster = _juglar_cluster(events, sung)
    if len(cluster) != len(JUGLAR_FINGERS):
        return
    base = int(events[cluster[0]].velocity or 0)
    for order, cursor in enumerate(cluster):
        events[cursor] = replace(
            events[cursor], velocity=max(40, min(72, base + JUGLAR_FINGERS[order]))
        )
```

Cluster chỉ quét `voice == 1`, nên ngón cái (voice 3) không bao giờ lọt vào và
`len(cluster)` đúng bằng 3. Bass **không** được chỉnh trong hàm này — nó không
thấy `low`, và arch còn nâng cú hát thêm 6–8 bậc sau đó, nên bass phải được ghi
lại ở một lượt riêng: mục 5.3.

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
                _respell_juglar_cluster(events, event)
```

Respell chạy cả khi `applied == 0`: lúc đó `base` vẫn là velocity gốc nên chùm
ra y hệt lúc render, nhưng nó xóa luôn phần lệch do `_shape_dynamics` để lại —
chùm Juglar luôn là `cú hát + fill`, không phụ thuộc câu nhạc đi qua hai bucket
eighth.

`cluster[0]` luôn là cú hát đã kẹp trần, vì mọi ngón trong một phách Juglar dùng
chung `midi` (một `_melody_at` cho cả ba). Ô cuối vùng (nốt đen) và `mode ==
"thin"` chỉ có một nốt mỗi phách nên `len(cluster) != 3` và thoát sớm, đúng ý.

### 5.3 Ghi lại ngón cái sau arch

`apply_torroba_sung_arch` chỉ nhận `lead`, nên không thể tự chỉnh bass. Nhưng arch
nâng cú hát tới 6–8 bậc (64 → 70), trong khi bass viết lúc render đã bị chặn ở
`max(ngón) + 2 = 66`; không ghi lại thì sau arch bass **tụt xuống dưới** cú hát,
đúng lỗi mà mục 5.1 vừa sửa. Vì vậy thêm một lượt ngay sau arch trong
`render_patterned_voices`:

```python
lead = apply_torroba_sung_arch(ctx, lead, patterns)   # dòng 3588, đã có
low = apply_juglar_thumb(ctx, lead, low, patterns)    # thêm
```

```python
def apply_juglar_thumb(ctx, lead, low, patterns):
    """Ngón cái hát lại 2 bậc trên chùm sau khi arch đã nâng ba ngón.

    Arch không nhận `low`, nên nếu thiếu lượt này thì bass viết lúc render tụt
    lại dưới cú hát vừa được nâng. Ghi lại đúng một lần, trên bản viết mà volume
    wave đọc sau đó.
    """
    from app.sonify.guitar_patterns import _bar_pattern

    lifted = list(low)
    for index, event in enumerate(lifted):
        if event.midi is None or event.velocity is None:
            continue
        if abs(event.beat - int(event.beat)) > 1e-9:
            continue
        if _bar_pattern(ctx, event.bar, patterns) != "torroba_tremolo":
            continue
        fingers = [
            int(note.velocity) for note in lead
            if note.voice == 1 and note.bar == event.bar and note.velocity is not None
            and event.beat - 1e-9 <= note.beat < event.beat + 1 - 1e-9
        ]
        if len(fingers) != len(JUGLAR_FINGERS):
            continue
        lifted[index] = replace(event, velocity=_juglar_thumb(fingers))
    return lifted
```

Ba điều kiện `continue` giữ lượt này vô hại: bass phải nằm đúng trên phách
(vòng bass của Juglar gọi `_fitting_bass` ở eighth 0/2/4, và các đường bass khác
của Torroba — `_half_bass_events`, `_bass_eighths_fit` — cũng chỉ đặt bass ở đầu
phách), ô phải là `torroba_tremolo`, và phách phải có đủ ba ngón (nhánh nốt đen
và `thin` chỉ có một ngón nên bỏ qua, bass vẫn nằm dưới bè giá như `_bed` viết).

Đây là lượt cuối trước `apply_guitar_wave`. Sau nó chỉ còn hai lượt chạm velocity:
wave (affine, cùng center cho cả ô nên giữ nguyên khoảng +2) và `_apply_stabs`
(`_STAB["low"] = 66`, chỉ ô khung outro, không phải ô Juglar).

Kết quả, `tmp/diag_juglar_cluster_plan.py`, 3/4, 96 BPM, rally, `mf`, ô 0:

| Tầng | Phách 0 | Phách 1 | Phách 2 |
|---|---|---|---|
| Hôm nay (viết) | 70 / 56 / 56 | 66 / 56 / 56 | 62 / 56 / 56 |
| Sau 5.1 + 5.3 (viết) | 70 / 67 / 66 (cái **72**) | 66 / 63 / 62 (cái **68**) | 62 / 59 / 58 (cái **64**) |
| Sau sóng (nghe) | 53 / 50 / 49 (cái **55**) | 49 / 46 / 45 (cái **51**) | 45 / 42 / 41 (cái **47**) |

Cú 2 so với cú 1 còn **94%** thay vì 74%, và phách vẫn nhô lên theo vòng câu (53, 49, 45). Đây là hình Barrios (`52 / 55 / 54 / 52`) đảo dấu: Barrios nhấn cú 2, Torroba nhấn cú 1 vì phách, cả hai đều là *waver*, không phải hai tầng rời nhau.

Trần 72 không còn là vấn đề: ngón 2–3 luôn thấp hơn cú hát đã kẹp, nên `min(72, ...)` chỉ chạm ở cú hát khi vòng câu muốn hơn 72. Ngón cái đứng **trên** nốt to nhất của chùm đúng 2 bậc, trước và sau sóng (72/68/64 trên 70/66/62; nghe 55/51/47 trên 53/49/45).


---

## 6. Chữ ký Juglar + Danza

Hôm nay chương 3/4 **rally** hát `Juglar — Danza — Juglar`; chương **calm** chỉ hát `Castillo — Juglar — Castillo` khi tempo ≤ 72, còn ở 96 thì rơi `Sonatina — Castillo — Sonatina` (mục 3). Sau khi bỏ cửa đó, cả hai chương đều có Juglar. Nhưng `Juglar — Danza — Juglar` cho 1M II ở 96 BPM nghĩa là hai slot A (48 ô, **90 giây**) gần như toàn tremolo, B chỉ 8–24 ô. Tai mỏi, và tremolo mất tính “bài ngắn”.

Chốt **một** luật, kiểm được bằng test:

1. **Chương 3/4 có Juglar thì phải có Danza hoặc Castillo làm khung.** Cụ thể: `torroba_tremolo` không bao giờ là primary duy nhất của một chương 3/4 — rally có `danza` làm contrast, calm có `castillo` làm khung. Đây là chữ ký của Torroba so với Barrios: tremolo **luôn** nằm trong một chương có điệu, không đứng một mình. Luật này đã đúng sau mục 3, và đã được khóa bằng `test_juglar_never_stands_alone_in_a_waltz_movement` (`tests/test_sonify_guitar_torroba.py`): ở 72 / 96 / 112 / 124 / 140 BPM, quét bốn mood, chương 3/4 chỉ hát Juglar ở calm, rally và volatile, và `primary != contrast` ở cả bốn.

Luật thứ hai từng có trong bản trước — chặn độ dài vùng Juglar bằng cách cho 8 ô cuối của vùng B hát `danza` — **bỏ khỏi phạm vi đợt này**. Nó đụng `_assign_macro`, tức đụng cả ba ensemble, để đổi một thứ mà mục 4 vừa làm cho *dễ nghe hơn*: vùng Juglar giờ là 12 cú/ô đều trên lưới móc kép, không còn bộ ba 3:2 dày đặc. Nghe lại `Castillo — Juglar — Castillo` ở 96 BPM trước đã; nếu vẫn mỏi thì bàn luật 2 như một thay đổi riêng, có doc riêng. Ghi lại đây để lần sau không ai tưởng nó bị bỏ sót.

Ba điều **không** làm:

- Không cho Juglar hát trên 4/4 hay 6/8. `_render_juglar_bar` rơi `_downbeat_only` ở đó, đúng như cũ.
- Không hạ tempo để tremolo “dày”: 96 BPM là đúng 6,4 cú/giây, xuống dưới là rời khỏi dải tremolo ngay.
- Không đổi `_grid_state`. `full` / `thin` vẫn như cũ; `pushed` của Juglar đã bị bỏ từ trước.


---

## 7. File đổi, test đổi, revision

**Code**

| File | Đổi |
|---|---|
| `backend/app/sonify/guitar_torroba.py` | `JUGLAR_FINGERS` / `JUGLAR_STEP` / `JUGLAR_RISE` / `JUGLAR_THUMB_FLOOR` / `JUGLAR_THUMB_CEIL` mới ở dòng ~32, **xóa `_TRIPLET` cùng dòng**; `_juglar_thumb` (công thức `max(ngón) + 2`) đặt cạnh chúng; `_torroba_primary` bỏ cửa `> 72`; `_torroba_contrast` bỏ cửa `> 72`; `_render_juglar_bar` viết ba ngón theo `JUGLAR_FINGERS` + bass búng lại mỗi phách qua `_fitting_bass` với `_juglar_thumb`, bỏ inner ở nhánh tremolo, giữ nguyên nhánh `quarter_notes`; **xóa `_one_under` (dòng 3710, chỉ có một chỗ gọi)**; sửa docstring `_render_juglar_bar` (3758–3762, đang viết “Eighth-note triplets” và “bass is one beat at eighth 0”); `_sung_attack` xóa nhánh `torroba_tremolo`; `_first_of_beat` mới + `apply_torroba_sung_arch` chọn ngón đầu và respell hai ngón sau; **`apply_juglar_thumb` mới** (5.3) đặt cạnh `apply_torroba_sung_arch`; `_edge_frame` bỏ `ctx.bpm <= 72` |
| `backend/app/sonify/span.py` | `retarget_torroba_tempo` mới cạnh `retarget_torroba_meter` (dòng 290); gọi ở `_framed_torroba` (319), `prepare_week` (1114), `prepare_year` (1237) |
| `backend/app/sonify/audio.py` | `SPAN_REVISION` `"69"` → `"70"` (dòng 43) — WAV cũ phải render lại |
| `backend/app/sonify/guitar_patterns.py` | **một dòng** ở dòng 3588: ngay sau `lead = apply_torroba_sung_arch(ctx, lead, patterns)` thêm `low = apply_juglar_thumb(ctx, lead, low, patterns)` (import cùng chỗ với `apply_torroba_sung_arch`) |
| `backend/tmp/diag_juglar_cluster_plan.py` | đã viết xong (chạy được, exit 0). **Không vá `app/`**: nó đọc thẳng `_render_juglar_bar`, `apply_torroba_sung_arch` và `apply_juglar_thumb` mà `render_patterned_voices` nối với nhau. Shim duy nhất là một `apply_guitar_wave` đồng nhất trong `main()`, để cùng một lần chạy in được mức viết cạnh mức nghe. `backend/tmp/` nằm trong `.gitignore`, nên đây là script đo tại chỗ, không vào commit |

`guitar_wave.py`, `guitar.py`, `guitar_frame.py` **không sửa**. `GUITAR_BPM['torroba']` giữ 96.

**Test**

| File | Dòng | Đổi |
|---|---|---|
| `tests/test_sonify_guitar_torroba.py` | 2995–3003 | `fast_waltz` (96 BPM) giờ ra `castillo` / `torroba_tremolo` như `waltz` ở 72. Gộp hai khối, thêm test khóa “tempo không đổi picker” cho 60/72/96/120/140 |
| | 3130–3205 | `test_juglar_triplets_accent_only_the_downbeat` → `test_juglar_chunk_is_one_thumb_and_three_fingers`. Trong khối này: 3146–3147 `len(support) == 1` + `support[0].midi < lead[0].midi` → `support == []` (nhánh tremolo bỏ inner); 3148 `[round(note.beat * 12) for note in low] == [0]` → `[round(note.beat) for note in low] == [0, 1, 2]`; 3149 `low[0].duration_beats == 1.5` → `all(note.duration_beats == pytest.approx(1.0) for note in low)`; thêm `[note.velocity for note in low] == [62, 74, 67]` (đo trên chính fixture này: `60/57/56`, `72/69/68`, `65/62/61`) và luật tổng quát `low[i].velocity == max(velocity ba ngón phách i) + 2` (luật 5.1 — bass hát trên chùm, `lead > bass` không còn đúng ở ô Juglar); 3153 tick `[quarter*12, quarter*12 + 4, quarter*12 + 8]` → `[quarter*12 + 3, quarter*12 + 6, quarter*12 + 9]` (ngón đầu nằm ở `0,25` = +3 phần 12; `attacks` chỉ lọc `lead`, giờ là ba ngón, không gồm ngón cái); 3155 `duration 0.25`; 3156 → `attacks[0].velocity > attacks[1].velocity > attacks[2].velocity` và `attacks[0].velocity - attacks[2].velocity == 4`; 3158 giữ (chỉ ngón đầu có accent, và chỉ phách 0); 3160 giữ (`ordinary` vẫn là velocity ngón đầu vì fill `0`); 3163 `round(beat * 12) % 4 == 0` → `round((beat % 1) * 4) in {1, 2, 3}`; 3164–3166 fixture `_is_target` `4 / 12` → `0.25`, beat `0.0` / `4 / 12` → `0.25` / `0.5`; 3171–3177 `thin_phrase` (câu phẳng, vẫn mode `full` nên vẫn 9 ngón): `len(thin_support) == 1` → `== 0`, `len(thin_lead) == 9` **giữ 9**, `len(thin_low) == 1` → `== 3`, duration `0.25`; 3174/3192/3199 `len(...) == 9` **giữ 9** (vẫn ba ngón mỗi phách); 3194 `downbeat` lọc `beat == 0.0` → `0.25`; 3201 `duration 0.25`. Thêm case `bpm=120`: tick vẫn `[+3, +6, +9]`, `duration 0.25` — hình không phụ thuộc tempo |
| | 3495–3503 | `juglar_lead`: `downbeat`/`last` lọc `beat == 0.0` / `2.0` → `0.25` / `2.25`; 3500 `4 / 12` → `0.25`. `last` là ngón **đầu** của phách 2 nên `velocity` vẫn `max(40, owned - 2)` |
| | 3208–3209 | **giữ nguyên**: `_shape_dynamics` không sửa, nên gap 4 vẫn là 4. Đây là test của hàm, không phải của `JUGLAR_FINGERS` |
| | 3211–3243 | **Test MusicXML, sẽ fail nếu không sửa**: 3233 `divisions=12` → `4`; 3241–3243 ba assert tuplet (`<actual-notes>3</actual-notes>`, `<normal-notes>2</normal-notes>`, `<normal-type>eighth</normal-type>`) → `xml.count("<type>16th</type>") == 9` và `"<time-modification>" not in xml`. `"<grace" not in xml` giữ. Đã đo bằng `score_to_musicxml` thật: chín nốt dài 0,25 ra `<type>16th</type>` ở **cả** `divisions=4` và `12`, và không có `<time-modification>` ở cả hai — nên ba assert cũ chắc chắn fail, không phải “có thể fail” |
| | 3701–3738 | `test_juglar_bar_before_the_return_stays_triplets` → `..._stays_a_chunk`: 3734 `len(earlier) == 9` **giữ 9**, 3735 `duration 0.25`; `earlier_low` `len == 1` / `1.5` → `len == 3` / `1.0` mỗi nốt; `earlier[0].accent` giữ; `last` (3737–3739, nốt đen) và `plan[69][0] == 9` giữ nguyên |
| | 4408–4438 | `test_juglar_flat_bar_steps_the_later_beats`: docstring 4409 bỏ chữ “triplets”, biến `triplets` → `fingers`; 4431 `len(attacks) == 3` **giữ 3**; 4432–4433 → `attacks[0].velocity == (64 if eighth == 0 else 62)`, `attacks[1].velocity == attacks[0].velocity - 3`, `attacks[2].velocity == attacks[0].velocity - 4`; 4434 `accent is (eighth == 0)` giữ; 4435–4437 nhánh `quarters` (nốt đen, ô cuối vùng) giữ nguyên `[64, 62, 62]` |
| | 3070–3096 | **Test khóa mục 6**, `test_juglar_never_stands_alone_in_a_waltz_movement`: 72 / 96 / 112 / 124 / 140 BPM × bốn mood, `primary != contrast`, và `torroba_tremolo` xuất hiện đúng ở calm, rally, volatile (selloff 3/4 không hát Juglar) |
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
| `tests/test_program.py` | 465–470, 494–498, 505–509 | Ba form dựng tay trong `test_torroba_day_week_and_chapters_follow_the_aba_tables` chuyển sang chuỗi thật `attach_frame(retarget_torroba_tempo(retarget_torroba_meter(spec, character), character), span)`, thêm import `retarget_torroba_tempo`. Chúng vẫn qua trước vì tự ghép `attach_frame` + `body`, nhưng test cũ khóa một đường mà code không còn đi (`1M` II không còn ở 72) |

`torroba[0]`, `torroba[2]` và `year[0]` đã ở hoặc trên sàn nên không đụng; `quarter[0]` chỉ đổi số `bpm`, câu `bars == bodies[0].bars + 12` vẫn đúng vì sàn không đổi số ô. Riêng `opening_rally` (dòng 456–460) mang character `selloff` nhưng sàn đọc mood **phiên đầu** là `rally` → 4/4 lên 120 thay vì 104; không test nào khóa số đó, và đây đúng là hành vi của cửa nhịp đang có.

`tests/test_sonify_guitar_torroba_doors.py` không đổi: fixture chỉ dùng `character="calm"` và `bpm=96`, không có `selloff`/`volatile`; cửa `_edge_frame` mà nó đi qua là mood calm nên không chạm nhánh `bpm <= 72`.

Ba nhóm **không** phải sửa, đã kiểm:

- Các test `divisions` (2645–2796) đều ép pattern `castillo` / `danza` / `fandanguillo` / `olite`, không có Juglar. Juglar giờ luôn là móc kép nên nó chỉ đòi `divisions = 4`; chương nào có Castillo làm khung thì 12 vẫn thắng do rasgueado của Castillo, và 0,25 × 12 = 3 nên cụm vẫn đứng đúng lưới 12.
- `assert_playable(score, profiles="torroba")` không có luật tốc độ cú, chỉ kiểm register / bàn tay / dây, nên 4 cú/phách (móc kép) qua bình thường.
- `_SUNG_ROWS`, `_CASTILLOS_WAVES` và profile sóng `("torroba", "torroba_tremolo")` (`guitar_wave.py` dòng 122) đọc theo `pattern` / `bar`, không theo số cú, nên không đụng.

---

## 8. Docs phải sửa

Bốn file, không phải ba. `sonify-guitar-torroba-plan.md` là bản plan cũ, đã bị
[`sonify-guitar-torroba-aba-tempo.md`](./sonify-guitar-torroba-aba-tempo.md) thay
ở phần chọn pattern, nhưng nó vẫn là nơi khai báo thang velocity `lead > bass >
inner`, nên vẫn phải sửa — không sửa thì mục 5.1 đảo ngược một luật mà file kia
vẫn còn ghi là tuyệt đối.

### 8.1 [`sonify-guitar-torroba-aba-tempo.md`](./sonify-guitar-torroba-aba-tempo.md)

- Dòng 17–20, bảng “Việc đang nghe”: I `4/4, 96` → `4/4, 104`; II `3/4, 72` →
  `3/4, 96`; III `6/8, 120` giữ; IV `4/4, 96` → `4/4, 120`.
- Dòng 18, 22: ba mốc `0:25–1:55 / 1:55–2:55 / 2:55–4:15` và mốc “2:50” phải
  **đo lại** sau khi render (1M II từ 240 xuống 180 giây, nên 2:50 không còn tồn
  tại). Đừng chép số cũ, cũng đừng tự chia tay — đọc từ file WAV mới.
- Dòng 26–30, bảng texture: dòng 28 `full` “Bộ ba 3:2 mỗi phách” → “ba chùm bốn
  cú p-a-m-i mỗi phách, ngón cái ở phách, ba ngón ở `+0,25 / 0,5 / 0,75`”; dòng 29
  `pushed` “Hai cú sau thấp hơn một nấc `_under_lead`” → “ba ngón theo
  `JUGLAR_FINGERS` (0 / −3 / −4), ngón cái hát **trên** nốt to nhất của chùm”;
  dòng 30 `thin` “Cú 2 và cú 3 nghỉ” → “ba ngón nghỉ, chỉ còn cú móc 0”.
- Dòng 32: đoạn “Lưới đang hát là một nốt đen mỗi phách … Bộ ba không được viết”
  mô tả trạng thái hôm nay và sẽ sai sau khi đổi: phần lớn câu `rise < 3` thành
  `full` (một chùm mỗi phách), chỉ ô cuối vùng và câu `thin` còn nốt đen.
- Dòng 74: "một nốt, không bộ ba" → "một nốt, không chùm" (chỉ là chữ, nhưng để
  nguyên thì lần sau lại đi tìm bộ ba).
- Dòng 76, 85, 94: ba header bảng `4/4, 90–108` / `3/4, 60–72` / `6/8, 108–120`
  → `4/4, 108–140` / `3/4, 96–124` / `6/8, 108–140`.
- Dòng 88: `rally | Juglar | Bộ ba tremolo trên 3/4` → “Ba chùm bốn cú trên 3/4”.
- Dòng 92: “1M II là 72. 3M II là 60. Chương giữa 1Y là 66.” → `96 / 96 / 96`.
- Dòng 101: “Scherzo 1Y (closer …) là 108” → `120`.
- Dòng 120, 122, 126: ba câu khẳng định “bộ ba” → “ba chùm bốn cú”; dòng 126
  giữ nguyên ý “giá đi ngang vẫn ra tremolo”.
- Dòng 132–135, bảng ACB 1M: `4/4 96` → `4/4 104`, `3/4 72` → `3/4 96`, `4/4 96`
  → `4/4 120`. Dòng 133 bỏ “Juglar đang thưa” và “thân Juglar là bộ ba”, còn
  “ô 69 là nốt đen”.
- Dòng 141: “bass Juglar không còn búng mỗi phách” **giữ** — sau đổi bass vẫn
  búng mỗi phách, chỉ khác là hát **trên** chùm.
- Dòng 149: bỏ câu “Kiểu 7 và kiểu 8 chỉ mở khi BPM ≤ 72” — code không còn cửa
  `bpm` nào để câu đó đúng.
- Dòng 151: `_juglar_hold` `bass_length=ctx.epb` → `bass_length=0.5` (một phách
  mỗi chùm), `_juglar_motor` giữ nguyên.
- Dòng 157: `Castillo — Juglar — Castillo (3/4, 72 BPM)` → `(3/4, 96 BPM)`.
- Dòng 173: “ô 68 … là bộ ba” → “ô 68 … là một chùm bốn cú”.

### 8.2 [`sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md)

- Mục 2, hàng `3/4, 60–72 BPM` → `3/4, 96–124 BPM`.
- Mục 3.1, dòng 102–118: bộ ba 3:2 → ba chùm bốn cú p-a-m-i. Cụ thể dòng 106
  (“Ba cú không rơi lên lưới móc đơn … `divisions = 12`”), 108 (“Cả bộ ba của
  một phách lấy một cao độ”), bảng 110–114 (`Cú | Tick trong phách`: 0 / 4 / 8 →
  `0 / 0,25 / 0,5 / 0,75` với 4 dòng), 118 (`thin`: “Cú 2 và cú 3 nghỉ”).
- Dòng 216: “móc 2 và móc 4 … thấp hơn một nấc `_under_lead`” → “ba ngón theo
  `JUGLAR_FINGERS`, ngón cái hát 2 bậc **trên** nốt to nhất của chùm”.
- Dòng 292, 294: cửa `torroba_tremolo` **không** đổi — cửa vẫn một cú mỗi đầu
  phách. Thêm một câu nói rõ: bộ ba/chùm chỉ thuộc thân bài, cửa giữ lưới móc
  đơn, để lần sau không ai “đồng bộ” cửa theo thân bài.

### 8.3 [`sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md) — bản cũ

- Mục 7, dòng 227 / 234 / 241: ba header bảng `90–108` / `60–72` / `108–120` →
  `108–140` / `96–124` / `108–140`, cùng phép đổi như 8.1.
- Dòng 24, 225: liệt kê BPM các chương — `1M` I là 104 sau retarget, `1Y` tháng
  12 là 120, `1D` giữ 96.
- Dòng 158, 191, 193: thang `lead > bass > inner` qua `_under_lead` thêm ngoại lệ
  **Juglar thân bài**: `bass > cú hát > ngón 2 > ngón 3` (mục 5.1), và nói rõ
  ngoại lệ chỉ áp cho `torroba_tremolo` trong 3/4.
- Đầu file: một dòng “phần chọn pattern đã bị
  [`aba-tempo.md`](./sonify-guitar-torroba-aba-tempo.md) thay; file này giữ vai
  trò thang velocity và hình học tay”.

### 8.4 [`sonify-guitar-torroba-dynamics.md`](./sonify-guitar-torroba-dynamics.md)

- Dòng 99: vòng câu chọn **ngón đầu của chùm** làm cú hát rồi respell hai ngón
  sau, không chỉ nâng cú đầu phách; và `apply_juglar_thumb` ghi lại ngón cái sau
  arch (`max(ngón) + 2`), nên ảnh hưởng của arch lên Juglar là **hai lượt**, không
  phải một.

### 8.5 File này

Trạng thái đã đổi sang **đã vào code** ở đầu file, kèm số đo mới từ
`tmp/diag_torroba_tempo.py`. Hai quyết định đã chốt, ghi lại đây:

- **Bỏ luật 2 của mục 6.** Không chặn độ dài vùng Juglar bằng 8 ô `danza` ở cuối
  vùng B: nó đụng `_assign_macro`, tức đụng cả ba ensemble, để đổi một thứ mà
  mục 4 vừa làm cho dễ nghe hơn. Vùng Juglar giờ là 12 cú/ô đều trên lưới móc
  kép. Nếu sau này vẫn thấy mỏi thì bàn lại như một thay đổi riêng, có doc riêng.
- **Bass lấy một nốt mỗi ô, rồi lặp lại.** `_render_juglar_bar` gọi
  `_sounding_bass` **một lần** cho cả ô; `_fitting_bass(..., (2, 1))` chỉ đổi
  sang một nốt bass khác của hợp âm khi ngón không với tới, không suy lại cao độ
  theo từng phách. Nhờ vậy ba phách cùng một dây bass, và ngón cái chỉ đổi **vận
  tốc** theo `_juglar_thumb`, không đổi cao độ.

---

## 9. Cách kiểm

```bash
cd backend
python tmp/diag_juglar_cluster_plan.py     # cụm Juglar trước/sau sóng, có và không có fill
python tmp/diag_torroba_tempo.py          # bảng cú/giây + velocity trước/sau sóng
PYTHONPATH=. python tmp/diag_torroba_specs.py   # bpm từng chương sau retarget
PYTHONPATH=. python tmp/diag_vic_1m_torroba.py  # cấu trúc 4 chương của một mã thật (cần mạng)
PYTHONPATH=. python tmp/diag_juglar_fast.py 120 # quét mã, in mọi chương 3/4 từ 112 BPM (cần mạng)
PYTHONPATH=. python tmp/diag_juglar_fast.py 112 1Y  # …cùng câu hỏi nhưng cho năm (mỗi chương 12 ô)
PYTHONPATH=. python tmp/summarize_juglar_fast.py /tmp/juglar_year.log # log → bảng, theo bpm
python -m pytest tests/test_span.py tests/test_sonify_guitar_torroba.py \
                 tests/test_sonify_guitar_torroba_doors.py -q
python -m pytest tests/ -k juglar -q      # vòng lặp ngắn khi đang sửa mục 3–5
python -m pytest tests/ -q -x             # SPAN_REVISION mới đụng test_ensemble
```

`tmp/diag_torroba_specs.py`, `tmp/diag_vic_1m_torroba.py` và `tmp/diag_juglar_fast.py` cần `PYTHONPATH=.` (chúng import `app.*` mà không tự thêm `backend` vào `sys.path`); hai diag đầu thì không.

`tmp/diag_vic_1m_torroba.py` và `tmp/diag_juglar_fast.py` đi qua `plan_span` nên cần mạng (Entrade OHLC) — chúng in đúng thứ mà `GET /v1/stocks/{symbol}/span?range=…&variant=guitar&ensemble=torroba` trả về, kể cả tên in, vì chúng render một lượt với `_HEADLINE` / `_FORM` để đọc pattern row như `_compose` làm.

`tmp/diag_juglar_cluster_plan.py` **không vá** `app/`: nó đọc thẳng `_render_juglar_bar`, `apply_torroba_sung_arch` và `apply_juglar_thumb` mà `render_patterned_voices` nối với nhau. Shim duy nhất còn lại là một `apply_guitar_wave` **đồng nhất** (trả lại `lead/support/low` nguyên vẹn) để cùng một lần chạy in được mức **viết** cạnh mức **nghe**; nó không đổi nốt, không đổi vận tốc, và chỉ sống trong `main()`. Bước 9 của mục 10 đã xong: ba dòng vá `_render_juglar_bar` / `apply_torroba_sung_arch` / chèn `planned_thumb` đã bỏ.

Bốn con số phải đọc được ở đầu ra `diag_torroba_tempo.py`:

1. 3/4 calm 96 BPM → **6,4 cú/giây**, không còn 4,8.
2. Chùm ô 0 → `[70, 67, 66]` (ngón cái **72**) trước sóng, `[53, 50, 49]` (ngón cái **55**) sau sóng.
3. `calm 3/4 96 BPM -> primary castillo  contrast torroba_tremolo` (không còn `sonatina`).
4. Mọi `spec.bpm` trong `[96, 140]`, và không chương nào nhỏ hơn giá trị cũ.

`tmp/diag_juglar_cluster_plan.py` in thêm những dòng đã đo được trên bản mô phỏng:
`divisions=4` ở cả năm tempo (72, 96, 112, 120, 140 — 72 chỉ còn là ca chịu lực,
sàn thật là 96), 12 cú/ô (3 ngón cái + 9 ngón), ngón cái đúng `max(ngón) + 2` ở
cả trước và sau sóng, và `assert_playable(score, profiles="torroba")` không ném ở
cả năm tempo.

Rồi nghe lại, xếp theo thứ tự dễ nghe ra lỗi nhất. Số đo ngày 2026-10-30 trên dữ liệu sống, nên chạy lại `tmp/diag_juglar_fast.py` trước khi nghe — nhân vật từng chương đổi theo tháng:

| Chương | Nhân vật | BPM | Cú/giây | Tên in | Nghe cái gì |
|---|---|---|---|---|---|
| `MSN 1M II` / `VHM 1M II` | volatile | 124 | 8,3 | `Danza — Juglar — Danza` | Đầu nhanh: chùm p-a-m-i phải thành một dải, không nghe ra từng nốt |
| `PVS 1M II` / `HDB 1M II` | rally | 112 | 7,5 | `Juglar — Danza — Juglar` | Juglar là A: câu mở đã tremolo, danza chỉ chen ở giữa |
| `VCB 1M I` / `MSN 1M I` | calm | 96 | 6,4 | `Castillo — Juglar — Castillo` | Đầu chậm: 12 cú/ô vẫn liền, ngón cái nghe rõ hơn ba ngón |
| `VHM 1Y` chương `08/26` | volatile | 124 | 8,3 | `Danza — Juglar — Danza` | Chương tháng dài 148 s ở đầu nhanh: nghe xem tremolo có mỏi tai qua cả ba slot không |

Mọi chương 3/4 nhanh nằm ở những ô **vốn đã** mang nhịp 3/4: `1M II`, `3M II`, và chương 2 / 5 / 8 / 11 của `1Y`. Ô 4/4 (I và IV của tháng, I và III của quý, chương 1 / 4 / 7 / 10 / 12 của năm) chỉ đổi sang 3/4 khi mood là `calm` hoặc `selloff`, mà hai mood đó bị sàn kéo xuống 96 / 104. Nên muốn nghe Juglar ở tempo nhanh thì luôn là chương II của `1M`/`3M` (hoặc ô 3/4 của `1Y`).

Quét 112 mã ngày 2026-10-30 (`tmp/diag_juglar_fast.py`):

- `1M` + `3M`: 423 chương 3/4, **87 chương từ 112 BPM trở lên, cả 87 hát Juglar** — 58 `Danza — Juglar — Danza` ở 124, 29 `Juglar — Danza — Juglar` ở 112, tất cả đều là chương II.
- `1Y`: 156 chương 3/4, **82 chương từ 112 BPM trở lên, cả 82 hát Juglar** — 54 ở 112, 28 ở 124, và lần quét này rơi cả vào chương `08/26` vì tháng 8 là ô 3/4 còn tháng 8/2026 thì tăng với toàn bộ 112 mã.

Hai mã `CCR`, `NAV` bị bỏ qua ở `1Y` (`a year needs one month with enough candles`). Danh sách in ở `tmp/juglar_fast_list.txt` và `tmp/juglar_year_list.txt`. Không có ngoại lệ nào: một chương 3/4 nhanh mà không hát Juglar là lỗi bảng mục 2.

---

## 10. Thứ tự làm

Mỗi bước phải xanh test trước khi sang bước sau. `pytest tests/ -k juglar -q` là
vòng lặp ngắn cho bước 3–5; cả bộ chỉ chạy ở bước 6.

1. ✅ `span.py` + hằng số floor + `_framed_torroba`: tempo vào đúng dải. Chạy `PYTHONPATH=. python tmp/diag_torroba_specs.py`, cập nhật `tests/test_span.py` (344–460). Hai test dựng form bằng tay — `tests/test_program.py` (ba form ở `test_torroba_day_week_and_chapters_follow_the_aba_tables`) và `tests/test_torroba_lowered_melody.py` (`_framed_day`, không dựng `FormSpec`) — không vỡ, nhưng form trong `test_program.py` đã đổi sang gọi `retarget_torroba_tempo(retarget_torroba_meter(...))` để không khóa một thứ code không còn làm.
2. ✅ Bỏ ba cửa `bpm` (`_torroba_primary`, `_torroba_contrast`, `_edge_frame`) và sửa docstring 41–43 / 80–82. Chạy lại diag: calm 3/4 ra `castillo` + `torroba_tremolo`. Cập nhật khối test 2995–3003. Bước này **không** đổi âm thanh (mục 3).
3. ✅ Trong `guitar_torroba.py`: hằng số `JUGLAR_FINGERS` / `JUGLAR_STEP` / `JUGLAR_RISE` / `JUGLAR_THUMB_FLOOR` / `JUGLAR_THUMB_CEIL` thay `_TRIPLET`; `_juglar_thumb`; `_render_juglar_bar` viết ba ngón theo `JUGLAR_FINGERS` rồi **vòng bass có `if quarter_notes`** (mục 4), bỏ inner ở nhánh tremolo; xóa `_one_under`; sửa docstring 3758–3762. Cập nhật test mật độ: 3130–3205, 3211–3243 (MusicXML, mục 7), 3495–3503, 3701–3738, 4408–4438.
4. ✅ `_first_of_beat` + nhánh tremolo trong `apply_torroba_sung_arch` (nhớ luật 48), rồi `_juglar_cluster` / `_respell_juglar_cluster` respell sau khi kẹp trần.
5. ✅ `apply_juglar_thumb` + `_juglar_thumb` (mục 5.3) và **một dòng** trong `guitar_patterns.py` (dòng 3588, ngay sau `apply_torroba_sung_arch`; import `apply_juglar_thumb` cùng chỗ). Chạy `tmp/diag_juglar_cluster_plan.py`, đo lại `[70, 67, 66]` (cái 72) trước sóng và `[53, 50, 49]` (cái 55) sau sóng, và kiểm ngón cái luôn `max(ngón) + 2`.
6. ✅ Bump `SPAN_REVISION` `"69"` → `"70"`, thêm test khóa luật mục 6 (`test_juglar_never_stands_alone_in_a_waltz_movement`), chạy cả bộ: `python -m pytest tests/ -q` → **734 passed**.
7. ✅ Sửa **bốn** file docs ở mục 8, đổi trạng thái file này.
8. ⏳ Nghe theo bảng ở mục 9: `MSN 1M II` (124, 8,3 cú/giây), `PVS 1M II` (112, 7,5), `VCB 1M I` (96, 6,4) — hoặc ô 3/4 của `1Y` (chương tháng 2 / 5 / 8 / 11) nếu muốn nghe tremolo nhanh trong một chương dài. Chương 3/4 nhanh chỉ có ở những ô vốn đã mang nhịp 3/4. VIC 1M hôm nay không có chương Juglar nào — bốn chương ra `selloff / selloff / volatile / rally` nên hát `Castillo — Danza — Castillo`, `Castillo — Danza — Castillo`, `Fandanguillo — Danza — Fandanguillo`, `Olite — Castillo — Olite` — nên đừng nghe VIC để kiểm tremolo; 1M I và 1M II của VIC đã render ở revision 70 và nghe được ngay. Luật 2 của mục 6 đã bỏ khỏi phạm vi; nếu sau khi nghe vẫn thấy mỏi thì mở một doc riêng cho `_assign_macro`. Đây là bước duy nhất còn lại — nó cần tai, không cần code.
9. ✅ Bỏ các dòng vá trong `main()` của `tmp/diag_juglar_cluster_plan.py` để nó đo code thật, chạy lại một lần cuối (exit 0, độc lập, không patch `app/`; chỉ còn shim `apply_guitar_wave` đồng nhất để in mức viết cạnh mức nghe).

