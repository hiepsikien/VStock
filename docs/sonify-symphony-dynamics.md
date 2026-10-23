# Dynamic và Cân bằng Âm lượng cho Giao hưởng & 12 Bộ Nhạc cụ

Kế hoạch này giải quyết hai bài toán đi liền nhau:
1. **Biểu cảm & phản ánh chuyển động thị trường (Market Movement)**: Đưa Flute (`P5`), Piano (`P3`) và Bass (`P4`) của Giao hưởng vào chung một hệ thống động lực học 3 tầng (Đà giá trong câu × Thanh khoản `p–f` × Tính cách phiên `BarGroove`), tương thích với cơ chế phát thực tế của MuseSounds trong MuseScore 4.
2. **Cân bằng âm lượng (Volume Balance) giữa các bè và trên toàn bộ 12 bộ nhạc cụ**: Loại bỏ tiếng Piano ẩn đánh chồng từ thẻ `<harmony>`, dọn dải tần trầm để Bass không đè Cello, và chuẩn hóa bảng gain `_VOICE_VOLUME_DB` trong `audio.py` cho tất cả 12 bộ nhạc cụ (`classic`, `wood`, `brass`, `soul`, `organ`, `mallet`, `guitar`, `breath`, `choir`).

---

## 1. Nguyên lý phát thực tế của MuseScore 4 + MuseSounds

Thực nghiệm xuất WAV qua `musescore_export` trên MuseScore 4.7.5 với thư viện MuseSounds (tính từ `0.0s` để bắt trọn transient đầu phách) cho thấy các quy luật vật lý của bộ sampler mà thiết kế phải bám sát:

1. **Cách MuseSounds phản ứng với `<direction><dynamics>`, `<wedge>` (lớp chính) và `<note dynamics="...">` (lớp phụ)**:
   - **Nhóm chỉ nghe chữ `<dynamics>` và `<wedge>`, bỏ qua 100% `<note dynamics="...">`**: Gồm cả các thư viện hơi, dây, đồng, hợp xướng (`Flute 1`, `Piccolo`, `Violins 1`, `Cellos`, `Oboe`, `Clarinet`, `Trumpet`, `Trombone`, `French Horns a6`, `Tuba`, `Contrabassoon`) **lẫn `Piano` (`Muse Keys`) và `Harp` (`Muse Harp`)**:
     - Thực nghiệm giữ nguyên `<p/>` và đổi `<note dynamics>` từ `51.11` (`vel=46`) lên `106.67` (`vel=96`):
       - `Piano`: đứng yên ở `-29.2 dB` Peak / `-46.2 dB` RMS; khi đổi chữ sang `<mp/>` tăng lên `-23.1 dB` Peak / `-40.2 dB` RMS (`+6.0 dB`), sang `<mf/>` tăng lên `-17.1 dB` Peak / `-34.6 dB` RMS (`+11.6 dB`).
       - `Harp`: đứng yên ở `-45.6 dB` Peak / `-64.1 dB` RMS; sang `<mp/>` tăng lên `-43.1 dB` Peak / `-61.6 dB` RMS, sang `<mf/>` tăng lên `-37.4 dB` Peak / `-55.4 dB` RMS.
       - `French Horns a6`: đứng yên ở `-24.3 dB` Peak / `-33.7 dB` RMS; sang `<mp/>` lên `-21.2 dB` Peak / `-30.7 dB` RMS, sang `<mf/>` lên `-18.2 dB` Peak / `-27.7 dB` RMS.
     - Do đó, `Piano`, `Harp` và `French Horns a6` **hoàn toàn đồng nhất về cơ chế phát trên MuseSounds** (chỉ nghe chữ in và `<wedge>`, không bao giờ bị cộng đúp hai lớp).
   - **Nhóm nhạc cụ gõ kim loại (`Glockenspiel`, `Crotales`, `Vibraphone`) nghe cả hai lớp**:
     - Trên `Glockenspiel` (ở `C6`): giữ `<p/>` và tăng `vel` từ `46` lên `96` làm Peak tăng từ `-45.7 dB` lên `-38.4 dB` (`+7.3 dB`); đổi chữ từ `<p/>` sang `<mp/>` ở cùng `vel=46` làm Peak tăng lên `-33.3 dB` (`+12.4 dB`).
   - **Quy luật "1 bậc tự động" của `<wedge>` không có chữ đích trên MuseScore 4**:
     - Đo trên `Flute 1` tại **cùng một cao độ `Đô6 (C6)`** để loại trừ sai lệch mẫu âm theo cao độ:

       | Cách viết trên `Flute 1` (cùng cao độ `Đô6`) | Peak | RMS | Nhận xét |
       |---|---|---|---|
       | `mp` phẳng (ô 1, từ im lặng) | `-38.0 dB` | `-47.9 dB` | Mức nền `mp` khi khởi âm |
       | `mp` + `crescendo` trần (không in `mf`) | `-25.4 dB` | `-38.5 dB` | Tăng đúng 1 bậc lên `mf` |
       | `mp` + `crescendo` + in `mf` ở cuối | `-25.3 dB` | `-38.2 dB` | Khớp với `crescendo` trần (lệch `0.1–0.3 dB`) |
       | `mp` + cặp `< >` (không in `mf` ở đỉnh) | `-22.9 dB` | `-36.5 dB` | Tự nở lên `mf` ở giữa rồi khép về `mp` |
       | `mp` + cặp `< mf >` (có in `mf` ở đỉnh) | `-22.9 dB` | `-36.3 dB` | **Bằng hệt `< >` không chữ `mf`** (lệch `0.2 dB`) |
       | Ô tiếp theo ngay sau `< >` (không in lại `mp`) | `-36.0 dB` | `-46.5 dB` | Tự trả về đúng mức `mp` liên tục |
       | Ô tiếp theo có in tường minh `<mp/>` | `-36.1 dB` | `-46.3 dB` | Khớp với ô sau `< >` (lệch `0.2 dB`) |

     - Đo tương tự trên `Piano` với câu Fill 4 nốt (`C4–E4–G4–C5`):

       | Cách viết câu Fill trên `Piano` | Peak cả ô | RMS cả ô | Peak nốt 1 $\rightarrow$ nốt 4 | Nhận xét |
       |---|---|---|---|---|
       | `<p/>` phẳng | `-26.9 dB` | `-40.4 dB` | `-29.2` $\rightarrow$ `-28.9 dB` | Mức giường `p` |
       | `<mp/>` phẳng | `-21.1 dB` | `-34.7 dB` | `-23.7` $\rightarrow$ `-23.1 dB` | Cao hơn `p` đúng 1 bậc (`+5.7 dB`) |
       | `<mf/>` phẳng | `-14.9 dB` | `-29.0 dB` | `-17.6` $\rightarrow$ `-17.1 dB` | Cao hơn `mp` đúng 1 bậc (`+5.7 dB`) |
       | Giường `<p/>` + `<crescendo>` (không in `<mp/>`) | `-24.1 dB` | `-37.6 dB` | **`-28.5` $\rightarrow$ `-24.1 dB`** | Nở mượt từ `p` lên đúng `mp` (+1 bậc) |
       | Giường `<mp/>` + `<crescendo>` (không in `<mf/>`) | `-18.4 dB` | `-31.9 dB` | **`-22.4` $\rightarrow$ `-18.4 dB`** | Nở mượt từ `mp` lên đúng `mf` (+1 bậc) |
       | In `<mf/>` đầu fill + `<crescendo>` | `-14.0 dB` | `-27.5 dB` | `-17.6` $\rightarrow$ **`-14.0 dB`** | Bị đẩy vọt 2 bậc từ giường `mp` lên `f`! |
       | In `<mp/>` đầu fill + `<diminuendo>` (trên giường `p`) | `-21.8 dB` | `-35.9 dB` | **`-23.4` $\rightarrow$ `-26.6 dB`** | Mở ở `mp` (+1 bậc trên `p`), nốt cuối giảm `3.2 dB` và còn ngồi trên giường `p` (`-29.2 dB`) `2.6 dB` |
       | In `<mf/>` đầu fill + `<diminuendo>` (trên giường `mp`) | `-16.2 dB` | `-30.5 dB` | **`-17.3` $\rightarrow$ `-20.7 dB`** | Mở ở `mf` (+1 bậc trên `mp`), nốt cuối giảm `3.4 dB` và còn ngồi trên giường `mp` (`-23.1 dB`) `2.4 dB` |

     - **Kết luận thiết kế từ thực nghiệm**:
       1. Trên Flute (`P5`): Một `<wedge type="crescendo">` từ `mp` đã tự động đạt đỉnh `mf` (`-22.9 dB` Peak / `-36.5 dB` RMS trên `C6`). Do đó:
          - Khi **`peak == 72`** (thanh khoản tại đỉnh là `p`/`mp` và không có `BREAKOUT` — câu yên): Flute **giữ chữ `"mp"` phẳng và không sinh `<wedge>`** (chỉ vuốt nhẹ `NoteEvent.velocity` từ `64` lên tối đa `72` cho MS Basic / `Glockenspiel`).
          - Chỉ khi **`peak == 80`** (thanh khoản tại đỉnh là `mf`/`f` hoặc có `BREAKOUT`): Flute mới sinh `<wedge>` theo 3 Hình thái, và không bao giờ cần in chữ `mf` ở đỉnh của Hình thái 1 và Hình thái 2 (nhờ đó `Glockenspiel` cũng không bị kích chữ `mf` ở giữa đoạn!). Chữ `mf` chỉ dùng để mở đầu Hình thái 3 (khi vào ngay tại đỉnh lúc `peak == 80` rồi `diminuendo`).
       2. Trên Piano Fill (`P3`): Vì `<crescendo>` tự nâng 1 bậc còn `<diminuendo>` giảm khoảng `3.2–3.4 dB` tính tới đầu nốt gõ cuối:
          - Khi fill có hướng **`Nở` (`rise`, $\ge 2$ nốt)**: **giữ nguyên chữ giường hiện tại (`p` hoặc `mp`) và chỉ mở `<crescendo>`** qua câu fill — âm lượng sẽ nở mượt từ mức giường lên đúng +1 bậc (`p -> mp` hoặc `mp -> mf`), đồng thời velocity trên nốt cũng đi từ đúng **velocity giường của ô đó (`bed_velocity_at[b]`: `46`/`54` hoặc `62`/`68`)** lên mức `fill_mark` (`64` hoặc `80`)!
          - Khi fill có hướng **`Lắng` (`fall`, $\ge 2$ nốt)**: **in chữ `fill_mark` (+1 bậc trên giường: `mp` trên `p`, hoặc `mf` trên `mp`) ở đầu fill kèm `<diminuendo>`** — câu fill vào nổi bật trên giường đúng 1 bậc rồi lắng xuống `3.2–3.4 dB` ở nốt cuối (nốt cuối vẫn đứng trên mức giường `2.4–2.6 dB` nên không bị chìm mất), sau đó hợp âm đệm ở `beat = 0.0` của ô kế tiếp in lại chữ giường để trả kênh `P3` về đúng mức giường!
          - Khi fill **`Ngang` (`flat`) hoặc chỉ có 1 nốt**: **in chữ `fill_mark` (+1 bậc trên giường), không kèm `<wedge>`**.

2. **Thẻ `<harmony>` trên `P3` khiến MuseScore 4 tự tổng hợp thêm một Piano ẩn đánh chồng lên phách 1 (+6.2 dB RMS / +6.7 dB Peak)**:
   - Trong `score.mscx` sinh ra từ MusicXML, mỗi thẻ `<harmony>` biến thành phần tử `<Harmony><harmonyInfo>...</harmonyInfo></Harmony>`. Khi xuất WAV ở trạng thái mặc định, MuseScore 4 tự gõ thêm một hợp âm Piano đầy đủ chồng lên phách 1: trên một ô 4/4 `120 BPM` chỉ có `P3` đánh hợp âm `Cmaj7` ở `p`, bản có `<Harmony>` mặc định phát ở **`-35.5 dB` RMS (`-18.4 dB` Peak)**, trong khi bản thêm `<play>0</play>` vào `<Harmony>` hoặc xóa `<Harmony>` phát đúng tiếng thật của nốt viết ở **`-41.7 dB` RMS (`-25.1 dB` Peak)** (khớp tuyệt đối đến `0.0 dB`).

---

## 2. Ba tầng chuyển động thị trường trên các bè Giao hưởng

| Tầng chuyển động | Flute / P5 (`classic`, `wood`, `brass`) | Violin & Cello (`P1`, `P2`) | Piano / P3 (`classic`, `wood`, `brass`) | Bass / P4 (`classic`, `wood`, `brass`) |
|---|---|---|---|---|
| **1. Giá trong câu** (`phrase.rise`, đỉnh, `BREAKOUT`) | Khi `peak == 80`: 1 nốt ngân dài $\ge 4$ móc nở `< >` ở giữa ngân; đoạn leo lên đỉnh chạy `< >` tới `span_apex`; vào ngay đỉnh mở `mf` rồi `>` | Giữ nguyên vòng cung `hairpins()` và `melody_parts()` hiện có; được tôn nổi nhờ Bass nhường dải tần và bảng `_VOICE_VOLUME_DB` | Fill `Nở` dùng `<crescendo>` + ramp velocity từ mức giường lên +1 bậc; Fill `Lắng` mở ở `fill_mark` (+1 bậc) kèm `<diminuendo>` lắng `3.2–3.4 dB` (vẫn trên giường `2.4–2.6 dB`) rồi ô sau trả về giường | Gập mọi nốt Bass `>= C3 (48)` xuống dưới `48` trên những ô Cello hát chính ($\ge \max(\text{nửa ô}, 2\text{ phách đen})$) |
| **2. Thanh khoản `p–f`** (`band_at`) | Band `mf`/`f` tại đỉnh hoặc `BREAKOUT` (`peak == 80`) mở `<wedge>` / chữ `mf` lên đỉnh `mf`; band `p`/`mp` không breakout (`peak == 72`) giữ `mp` phẳng (không `<wedge>`) | Velocity và nốt nhấn phản ánh câu | Chữ in giường (`p` cho `p`/`mp`, `mp` cho `mf`/`f`), 4 bậc velocity (`46 / 54 / 62 / 68` cho MS Basic), và tay trái điểm gốc mỗi ô ở `f` | Mật độ tiết tấu từ tròn (`p`) tới 8 móc đơn (`f`), chữ in trần `mp` |
| **3. Tính cách phiên (`BarGroove`)** | `BREAKOUT` luôn đặt `peak = 80` (bật `<wedge>` / `mf`) | `selloff` nhường sớm vùng trung-trầm cho Cello | Đọc `chamber`, `trio_thin`, `half`, `rally`, `selloff`, `caesura`; gốc tay trái đánh mỗi ô khi `f` hoặc `rally` | Đọc `chamber`, `trio_thin`, `half`, `tresillo`, `selloff`, `rally`, `caesura` |

---

## 3. Flute (`P5`): State Machine cho chữ Dynamic, Hairpin và Velocity

Flute vào khi câu lên cao (`>= FLUTE_TRIGGER`), khi có `BREAKOUT`, hoặc khi nốt vượt trần violin (`violin_ceiling`). `_flute_and_violin_dovetail` ghi `yield_spans` và dựng vòng cung cho đúng đoạn `[span_start, sounding_end)` mà Flute hát.

### A. Định nghĩa chính xác các biến của một đoạn Flute `[span_start, sounding_end)`

1. **`span_apex` (tie-break khi có cao nguyên giá)**:
   - Lấy từ đường giá gốc `pitches[eighth]` (trước khi `flute_harmony_pitch` cộng quãng và gập trần `Mi6`), và **lấy móc đơn đầu tiên đạt giá trị cực đại** trong đoạn (đồng nhất với `Phrase.apex`):
     ```python
     span_apex = max(range(span_start, sounding_end), key=lambda e: (pitches[e], -e))
     ```
2. **Cờ `has_breakout` của đoạn và `overlaps_breakout(start, end)`**:
   - Kiểm tra `BREAKOUT` bằng phép giao khoảng thời gian `[start, end)` với các run của `phrase.runs`:
     ```python
     def overlaps_breakout(start: int, end: int) -> bool:
         return any(
             colours.get(r.start) == BREAKOUT
             for r in phrase.runs
             if r.end > start and r.start < end
         )

     has_breakout = overlaps_breakout(span_start, sounding_end)
     ```
3. **Mức `peak` của đoạn**:
   - Luôn tra `band_at` tại ô của `span_apex` gốc (`apex_bar = span_apex // epb`):
     ```python
     peak = 80 if (has_breakout or band_at[span_apex // epb] in ("mf", "f")) else 72
     ```
4. **Ranh giới câu nối dây (`tie_first_in` / `held_over`)**:
   - Nếu `tie_first_in == True` (nốt đầu đoạn buộc nối từ cuối phrase trước), run đầu tiên (`r_i == 0`) là nốt nối dây (`tie_stop=True`), không phải tiếng đánh mới; mọi chữ dynamic in lại hoặc mở mới chỉ được đặt trên **run đầu tiên có tiếng đánh mới** (`first_attack`, tức run đầu tiên có `not (r_i == 0 and tie_first_in)`). Nếu cả đoạn chỉ có 1 run duy nhất và `tie_first_in == True` thì `first_attack = None`: đoạn này chỉ ngân nốt nối dây, không sinh chữ mới và không mở `<wedge>`.

### B. Thứ tự ưu tiên giữa `Glockenspiel` và 3 Hình thái của Flute

Với mỗi đoạn Flute có `sounding_end > span_start` và `first_attack is not None`, đặt `arc_start = first_attack.start`:

- **Nhánh A — Đoạn không sinh `<wedge>` (`phrase.rise < MIN_RISE` hoặc `peak == 72` hoặc `sounding_end - arc_start < WEDGE_MIN`)**:
  - Không sinh `<wedge>` (câu phẳng, câu có `peak == 72`, hoặc đoạn 1 móc không đủ chỗ cho vòng cung).
  - **Chữ mở đoạn (`start_marking`)**:
    - Nếu `ensemble == "brass"` (`Glockenspiel`), `len(merged_flute_runs) == 1`, `phrase.rise >= MIN_RISE` và `peak == 80` (kể cả khi đoạn chỉ dài 1 móc): `start_marking = "mf"` (để tiếng chuông đơn ở đỉnh `mf`/`f` hoặc `BREAKOUT` vang đúng mức `mf`, thuộc Trường hợp 2 của bảng chuyển trạng thái).
    - Mọi trường hợp còn lại của Nhánh A (bao gồm `Flute 1` và `Piccolo` trên đoạn 1 móc `sounding_end - arc_start < WEDGE_MIN`, mọi đoạn `peak == 72`, và mọi đoạn `phrase.rise < MIN_RISE`): `start_marking = "mp"` (thuộc Trường hợp 1 của bảng chuyển trạng thái).
  - **Về `velocity`**:
    - Nếu `phrase.rise < MIN_RISE`: mọi nốt trong đoạn giữ `velocity = 64`.
    - Nếu `phrase.rise >= MIN_RISE`:
      - Với `Glockenspiel` 1 run (`ensemble == "brass"` và `len(merged_flute_runs) == 1`): gán `velocity = peak` (`72` khi `peak == 72`, `80` khi `peak == 80`).
      - Với sáo (`classic` / `wood`) trên đoạn 1 móc ở `peak == 80`: run giao với `BREAKOUT` (`overlaps_breakout`) nhận `velocity = 80`, ngược lại tính theo `span_swell` (tại `eff_apex = span_apex`, tức nhận `round(64 + 16 * lift(phrase))`).
      - Với `peak == 72`: vuốt nhẹ `NoteEvent.velocity` trong khoảng `64..72` theo `span_swell` (với `eff_apex = arc_start + (sounding_end - arc_start) // 2` nếu 1 run dài $\ge 4$ móc, ngược lại `eff_apex = span_apex`).

- **Nhánh B — Đoạn có độ dốc, đủ độ dài VÀ `peak == 80` (`phrase.rise >= MIN_RISE` và `sounding_end - arc_start >= WEDGE_MIN` và `peak == 80`)**:
  Kiểm tra theo đúng thứ tự ưu tiên từ 1 đến 4 (không in chữ `"mf"` ở đỉnh của Hình thái 1 và 2 vì `<wedge>` từ `"mp"` đã tự động đạt đỉnh `"mf"` trên MuseSounds):
  1. **Ưu tiên 1 — `Glockenspiel` 1 tiếng gõ (`ensemble == "brass"` và `len(merged_flute_runs) < 2`)**:
     - Không sinh `<wedge>` (nhạc cụ gõ kim loại tắt dần sau cú gõ).
     - Gán `velocity = 80`, và yêu cầu `start_marking = "mf"` (thuộc Trường hợp 2 của bảng chuyển trạng thái).
  2. **Ưu tiên 2 (Hình thái 2) — Một cao độ sáo ngân dài duy nhất (`len(merged_flute_runs) == 1` và `sounding_end - arc_start >= 4`)**:
     - Đặt đỉnh vào giữa hơi ngân: `eff_apex = arc_start + (sounding_end - arc_start) // 2`, `start_marking = "mp"`.
     - Sinh `wedges = hairpins(arc_start, sounding_end, eff_apex)` (luôn đủ $\ge 2$ móc mỗi bên nên luôn có đủ cặp `< >` nở từ `mp` lên `mf` rồi khép về `mp`).
  3. **Ưu tiên 3 (Hình thái 1) — Đoạn leo lên đỉnh (`span_apex - arc_start >= WEDGE_MIN`)**:
     - `eff_apex = span_apex`, `start_marking = "mp"`.
     - Sinh `wedges = hairpins(arc_start, sounding_end, eff_apex)` (gồm `crescendo` từ `arc_start` tới `eff_apex`, và `diminuendo` từ `eff_apex` tới `sounding_end` nếu `sounding_end - eff_apex >= WEDGE_MIN`).
  4. **Ưu tiên 4 (Hình thái 3) — Vào ngay tại đỉnh rồi đi xuống (`span_apex - arc_start < WEDGE_MIN`)**:
     - `eff_apex = arc_start`.
     - Với `ensemble == "brass"` (`Glockenspiel`, vốn nghe cả chữ lẫn velocity): giữ `start_marking = "mp"` và mở `diminuendo` (`>`) từ `arc_start` tới `sounding_end` để chuỗi tiếng chuông giảm dần theo velocity mà không bị chữ `"mf"` kích vọt `+14 dB` ở đầu đoạn.
     - Với `classic` (`Flute 1`) và `wood` (`Piccolo`): yêu cầu `start_marking = "mf"` ngay tại `arc_start` (đón tiếp đỉnh cao trào từ Violin) rồi sinh `wedges = [_wedge_at(arc_start, "diminuendo"), _wedge_at(sounding_end, "stop")]`.

### C. State Machine duy nhất quản lý chữ in (`high_dynamics`), Bảng chuyển trạng thái và chống trùng ở `bar == 0`

`_flute_and_violin_dovetail` duy trì biến trạng thái `effective_level: str = "mp"` (nhận `"mp"` khi kênh P5 đang đứng ở mức `mp` chuẩn, hoặc `"drifted"` khi kênh P5 vừa rời khỏi `mp` do chữ `"mf"` hoặc do một `<wedge>` bất đối xứng):

```python
# Khởi tạo đầu bài (ứng với opening_dynamic = "mp" ở bar 0, beat 0.0):
effective_level = "mp"

def emit_flute_dynamic(eighth_pos: int, target_marking: str) -> None:
    nonlocal effective_level
    if effective_level == target_marking:
        return
    bar = eighth_pos // epb
    beat = (eighth_pos % epb) * 0.5
    flute_dynamics.append(
        DynamicEvent(bar=bar, marking=target_marking, sound=SOUND[target_marking], beat=beat)
    )
    effective_level = target_marking
```

**Bảng chuyển trạng thái `effective_level` cho cả 4 cách kết thúc một đoạn Flute**:

| Cách thực thi của đoạn Flute | Lệnh gọi `emit_flute_dynamic` trong đoạn | Giá trị `effective_level` sau khi kết thúc đoạn | Hệ quả ở đoạn Flute kế tiếp (có `first_attack`) |
|---|---|---|---|
| **1. Không có `<wedge>` và đứng ở `"mp"`**<br>*(Đoạn phẳng `rise < MIN_RISE`, mọi đoạn `peak == 72`, hoặc đoạn `< WEDGE_MIN` của sáo `classic`/`wood`)* | `emit_flute_dynamic(arc_start, "mp")` | **`"mp"`** | Đoạn sau mở `"mp"` sẽ không in lặp `"mp"`; đoạn sau mở `"mf"` sẽ in `"mf"`. |
| **2. Không có `<wedge>` nhưng mở `"mf"`**<br>*(`Glockenspiel` 1 run với `rise >= MIN_RISE` và `peak == 80`, kể cả khi dài 1 móc `< WEDGE_MIN` hay $\ge \text{WEDGE\_MIN}$)* | `emit_flute_dynamic(arc_start, "mf")` | **`"drifted"`** | Đoạn sau bắt buộc in lại `"mp"` (nếu `start_marking == "mp"`) hoặc in `"mf"` (nếu `start_marking == "mf"`). |
| **3. Có cặp `< >` cân bằng đủ hai cạnh trên nền `"mp"`**<br>*(Nhánh B `peak == 80`: Hình thái 2, hoặc Hình thái 1 khi `sounding_end - eff_apex >= WEDGE_MIN`)* | `emit_flute_dynamic(arc_start, "mp")` | **`"mp"`** | Thực nghiệm Mục 1 chứng minh sau `< >` cân bằng, mức phát tự trả về `-46.5 dB` RMS (khớp `<mp/>` tường minh `-46.3 dB` RMS, giống `drift == 0` của Violin/Cello), nên đoạn sau mở `"mp"` không cần in thừa chữ. |
| **4. Đoạn chỉ có 1 cạnh `<wedge>` (bất đối xứng)**<br>*(Nhánh B `peak == 80`: **(4a)** Hình thái 1 kết thúc ngay tại đỉnh chỉ có `crescendo` trần `sounding_end - eff_apex < WEDGE_MIN`; **(4b)** Hình thái 3 mở `"mf"`/`"mp"` rồi chỉ có `diminuendo`)* | • **(4a)**: `emit_flute_dynamic(arc_start, "mp")`<br>• **(4b)**: `emit_flute_dynamic(arc_start, start_marking)` | **`"drifted"`** | Vì `"drifted"` khác cả `"mp"` lẫn `"mf"`, đoạn kế tiếp **luôn in tường minh** `start_marking` của nó (`"mp"` để reset về nền, hoặc `"mf"` nếu đoạn kế tiếp là Hình thái 3 ở `peak == 80`!). |

- **Lưu ý thực thi**: Bản thân lệnh `emit_flute_dynamic` gán `effective_level = target_marking`, nên ở Trường hợp 2 và Trường hợp 4, **ngay sau khi xử lý xong đoạn phải có lệnh gán tường minh `effective_level = "drifted"`**.
- **Chống trùng ở `bar == 0, beat == 0.0` (chỉ áp dụng cho `P5` và `P3`)**: Trong `musicxml.py`, giữ nguyên `_opening_p` cho `P1` (Violin) và `P2` (Cello). Viết hàm `_opening_dynamic(dynamics, default)` chỉ dùng cho `P5` và `P3` của Giao hưởng: nếu phần tử đầu tiên của `dynamics` nằm tại `(bar=0, beat=0.0)`, dùng phần tử đó làm `opening_dynamic` của part và trả về `dynamics[1:]`, đảm bảo ô 1 không bao giờ có 2 thẻ `<dynamics>`.

### D. Công thức `span_swell(onset)` cho `NoteEvent.velocity`

- Với mỗi run `f_run` trong `merged_flute_runs` của đoạn có `phrase.rise >= MIN_RISE` và `first_attack is not None`, đặt `onset = max(arc_start, f_run.start)`:
  - Nếu là `Glockenspiel` 1 run (`ensemble == "brass"` và `len(merged_flute_runs) == 1`): `vel = peak` (`72` hoặc `80`, không đi qua `span_swell`).
  - Ngược lại, nếu `overlaps_breakout(f_run.start, f_run.end)`: `vel = peak` (`80`).
  - Ngược lại:
    - Nếu `onset <= eff_apex`: `s = 1.0 if eff_apex == arc_start else (onset - arc_start) / (eff_apex - arc_start)`
    - Nếu `onset > eff_apex`: `s = 1.0 - (onset - eff_apex) / max(1, sounding_end - eff_apex)`
    - `vel = round(64 + (peak - 64) * lift(phrase) * s)`
- Nếu `f_run` là run nối dây từ câu trước (`r_i == 0 and tie_first_in`) và câu hiện tại phẳng (`phrase.rise < MIN_RISE`), `vel = 64`.

---

## 4. Violin (`P1`), Cello (`P2`) và Bass (`P4`): Phạm vi giữ nguyên & Quy tắc Bass nhường Cello

### A. Giữ nguyên `melody_parts()` của Violin và Cello

- Giữ nguyên 100% logic `hairpins()`, `drift` và velocity của `melody_parts()` trong `backend/app/sonify/phrasing.py` để bảo toàn toàn bộ các bài test hiện hữu.
- Violin và Cello được cải thiện độ rõ nét và cân bằng âm lượng thông qua:
  1. Bảng gain `_VOICE_VOLUME_DB` (`Violins 1: +2 dB`, `Cellos: +4 dB`, `Electric Bass: -6 dB`).
  2. Quy tắc Bass gập toàn bộ nốt `>= Đô3 (48)` xuống dưới `Đô3` ở các ô Cello hát chính dưới đây.

### B. Quy tắc chính xác để Bass (`P4`) nhường trọn dải tần `>= Đô3 (48)` cho Cello (`P2`)

1. **Ngưỡng xác định "ô có Cello hát chính" (`cello_lead_bars`)**:
   - Để các nốt dovetail lead-in / trail-out ngắn (1–2 móc đơn ở `4/4`, hoặc đoạn 3 móc đơn `MIN_VIOLIN_SPAN` ở `6/8`) không làm mất quãng 8 của Bass ở những ô Violin đang hát chính, một ô `bar` chỉ được tính vào `cello_lead_bars` khi tổng thời lượng các nốt có cao độ của Cello trong ô đó đạt **ít nhất `max(active_meter().quarter_beats / 2, 2.0)` phách đen** (tức tối thiểu `2.0` phách đen = `4` móc đơn trên mọi nhịp `4/4`, `3/4`, `6/8`):
     ```python
     min_cello_beats = max(active_meter().quarter_beats / 2, 2.0)
     cello_beats_by_bar: dict[int, float] = {}
     for note in cello.notes:
         if note.midi is not None:
             cello_beats_by_bar[note.bar] = cello_beats_by_bar.get(note.bar, 0.0) + note.duration_beats
     cello_lead_bars = {bar for bar, beats in cello_beats_by_bar.items() if beats >= min_cello_beats - 1e-6}
     ```
2. **Giữ toàn bộ nốt Bass nghiêm ngặt trong vùng `Đô2–Si2 (36–47)` khi `under_cello=True`**:
   - Khi `under_cello == True`:
     - Trong `_bass_pattern`: thay bước `OCTAVE` bằng `ROOT` (cùng nhánh với `groove.selloff`).
     - Trong `_bass_bar(chord, marking, bar, *, under_cello: bool = False)`: nếu `under_cello` là `True` và cao độ `midi` của bất kỳ nốt Bass nào vẫn `>= 48` (`Đô3`, xảy ra ở bậc `FIFTH` của các hợp âm `F, G, Ab, A, Bb, B`), hạ nốt đó xuống một quãng 8 (`midi - 12` nếu `midi - 12 >= 36`, ngược lại về `chord.bass_midi`).
   - Nhờ vậy, trên mọi ô Cello hát chính (kể cả khi thanh khoản ở `mf` hay `f`), 100% các nốt của Bass đều nằm gọn trong `36..47` (`Đô2–Si2`), nhường sạch quãng `>= Đô3 (48)` cho Cello.

---

## 5. Piano (`P3`): Plumbing hàm, Chữ giường, `<wedge>` + Nội suy cho Fill và `<Harmony><play>0</play>`

### A. Tắt phát tiếng Piano ẩn của `<harmony>` trong `.mscz` và hành vi ở đường MS Basic

1. **Thao tác XML trên `score.mscx` trong `_assign_installed_sounds` (`backend/app/sonify/audio.py`)**:
   - Dùng phép thay thế regex chính xác trên từng khối `<Harmony>...</Harmony>` để chèn `<play>0</play>` mà không làm thay đổi định dạng XML gốc của `score.mscx`:
     ```python
     _HARMONY_BLOCK = re.compile(r"<Harmony\b[^>]*>.*?</Harmony>", re.DOTALL)

     def _mute_mscx_harmony(mscx_bytes: bytes) -> bytes:
         try:
             text = mscx_bytes.decode("utf-8")
         except UnicodeDecodeError:
             return mscx_bytes
         def _inject(match: re.Match[str]) -> str:
             block = match.group(0)
             if "<play>" in block:
                 return re.sub(r"<play>\s*[^<]*\s*</play>", "<play>0</play>", block)
             return block.replace("</Harmony>", "<play>0</play></Harmony>", 1)
         updated = _HARMONY_BLOCK.sub(_inject, text)
         return updated.encode("utf-8") if updated != text else mscx_bytes
     ```
2. **Hành vi ở đường fallback MS Basic (`use_config == True` hoặc `library == {}`)**:
   - Chấp nhận giữ nguyên hành vi MS Basic hiện tại khi không qua bước `.mscz`.

### B. Plumbing cho Piano (`_right_hand`, `left_hand`, `fills`), `<wedge>` trên Fill đồng bộ từng ô

1. **`left_hand` trong `backend/app/sonify/phrasing.py`**:
   - Thêm 2 tham số keyword-only tùy chọn `velocity_at: dict[int, int] | None = None` và `every_bar_at: frozenset[int] = frozenset()` (mặc định giữ nguyên 100% hành vi của `jazz.py`).
   - Trong mỗi ô của slot, thứ tự là: `warmup` / `cooldown` luôn đánh; rồi `bar in every_bar_at` đánh lại gốc, kể cả ô giữa một slot `outro`; rồi slot `outro` chỉ đánh khi `offset == 0`; các slot còn lại đánh khi `offset % 2 == 0`. Giao hưởng truyền `every_bar_at` gồm mọi ô có `effective_comp_band == "f"` hoặc `groove_at(bar).rally`. Jazz gọi `left_hand(slot)`, tập đó rỗng, nên outro vẫn chỉ đánh một lần.
2. **Hạ band theo Groove (`effective_comp_band`) và bảng `PIANO_VELOCITY` trong `dynamics.py`**:
   - `effective_comp_band(band: str, bar: int | None = None) -> str` áp dụng đúng 3 nhánh `chamber`, `trio_thin`, `half`.
   - `piano_marking(eff_band)` trả về `"p"` cho `"p"/"mp"`, và `"mp"` cho `"mf"/"f"`.
   - `PIANO_VELOCITY = {"p": 46, "mp": 54, "mf": 62, "f": 68}`.
3. **Nâng cấp `_right_hand` trong `render.py` — đồng bộ chữ, `<wedge>` và nội suy velocity theo từng ô `b` (`sub_group`)**:
   - Đổi chữ ký `_right_hand`:
     ```python
     def _right_hand(
         slots: tuple[ChordSlot, ...],
         cadence_fills: list[tuple[int, int, int]],
         piece_eighths: int = TOTAL_EIGHTHS,
         *,
         bed_velocity_at: dict[int, int] | None = None,
         bed_marking_at: dict[int, str] | None = None,
         phrases: tuple[Phrase, ...] | None = None,
     ) -> tuple[tuple[NoteEvent, ...], list[tuple[int, float, str, bool]], list[WedgeEvent]]:
     ```
   - Khi gọi với mặc định `bed_velocity_at=None` (`test_chamber_bar_drops_the_symphony_right_hand`): guide tones giữ `velocity=None`, fill giữ `FILL_VELOCITY = 64`, trả về `(notes, [], [])`.
   - Khi gọi từ nhánh `symphony` của `_compose`:
     - Guide tones ở ô `bar` nhận `velocity = bed_velocity_at[bar]`.
     - Các tuple `(start, length, midi)` của `cadence_fills` sau khi lọc bỏ nửa sau ô `caesura` được gom lại theo từng `phrase` đóng (`phrase.closes`), rồi **tách thành các `sub_group` theo từng ô nhịp `b = start // epb`** để cả chữ in, `<wedge>` lẫn nội suy velocity luôn đồng bộ trên cùng một ô `b` (kể cả khi câu fill bước qua vạch ô từ band `p` sang band `mf`!).
     - Với mỗi `sub_group` trên ô `b` (có `m_b = len(sub_group)` runs, bắt đầu tại `sub_start = sub_group[0][0]`, kết thúc tại `sub_end = sub_group[-1][0] + sub_group[-1][1]`, phách bắt đầu `fill_beat = (sub_start % epb) * 0.5`):
       - **Hướng vuốt (`direction`)**:
         - Nếu `groove_at(b).selloff`: `"fall"` (`Lắng`).
         - Ngược lại, nếu `groove_at(b).rally`: `"rise"` (`Nở`).
         - Ngược lại, so sánh `phrase.cadence.midi` với `phrase.runs[0].midi`: `>` thì `"rise"`, `<` thì `"fall"`, `==` thì `"flat"` (`Ngang`).
       - **Mức giường và mức đích của fill tại ô `b`**:
         - `bed_mark = bed_marking_at[b]` (`"p"` hoặc `"mp"`).
         - `fill_mark = "mp" if bed_mark == "p" else "mf"`.
       - **Quy tắc kết hợp Chữ và `<wedge>` để luôn nâng đúng +1 bậc trên MuseSounds (theo bảng đo `M1..M8` ở Mục 1)**:
         1. **Khi `m_b >= 2` và `sub_end - sub_start >= WEDGE_MIN` và `direction == "rise"` (`Nở`)**:
            - Vì `<wedge type="crescendo">` trên Piano đã tự động nâng đúng +1 bậc từ mức hiện tại (`p -> mp` hoặc `mp -> mf`), **chữ bắt đầu tại `fill_beat` là `bed_mark`** (tức giữ nguyên mức giường của ô `b`, không nâng sẵn lên `fill_mark` để tránh bị cộng thành +2 bậc lên `f`!), kèm mở `<wedge type="crescendo">` tại `sub_start` và đóng `stop` tại `sub_end`.
            - Ghi nhận sự kiện fill `(b, fill_beat, bed_mark, True)` (`has_wedge = True`).
         2. **Khi `m_b >= 2` và `sub_end - sub_start >= WEDGE_MIN` và `direction == "fall"` (`Lắng`)**:
            - Cần câu fill vào nổi bật trên giường đúng +1 bậc rồi lắng xuống: **chữ bắt đầu tại `fill_beat` là `fill_mark`** (`"mp"` trên giường `"p"`, hoặc `"mf"` trên giường `"mp"`), kèm mở `<wedge type="diminuendo">` tại `sub_start` và đóng `stop` tại `sub_end` (theo phép đo `M6` và `M8`, câu fill giảm `3.2–3.4 dB` tới nốt gõ cuối, vẫn đứng cao hơn mức giường `2.4–2.6 dB` để nốt kết fill không bị chìm, sau đó đầu ô kế tiếp in lại chữ giường).
            - Ghi nhận sự kiện fill `(b, fill_beat, fill_mark, True)` (`has_wedge = True`).
         3. **Khi `m_b == 1` hoặc `sub_end - sub_start < WEDGE_MIN` hoặc `direction == "flat"` (`Ngang`)**:
            - Không sinh `<wedge>`. **Chữ bắt đầu tại `fill_beat` là `fill_mark`** (+1 bậc trên giường).
            - Ghi nhận sự kiện fill `(b, fill_beat, fill_mark, False)` (`has_wedge = False`).
       - **Công thức nội suy tuyến tính cho `NoteEvent.velocity` trên chính `sub_group` (`m_b` nốt trong ô `b`) — đi cùng chiều với chữ in**:
         - Đặt `bed_vel = bed_velocity_at[b]` (`46`/`54` khi giường `p`, hoặc `62`/`68` khi giường `mp`), và `target_vel = 64 if fill_mark == "mp" else 80`.
         - Nếu `m_b == 1` hoặc `sub_end - sub_start < WEDGE_MIN` hoặc `direction == "flat"` (`Ngang`): mọi nốt trong `sub_group` nhận `vel_k = target_vel` (`64` hoặc `80`, khớp với chữ `fill_mark` không có wedge).
         - Nếu `m_b >= 2` và `sub_end - sub_start >= WEDGE_MIN`:
           - Với `direction == "rise"` (`Nở` — mở từ mức giường rồi `<crescendo>` lên `fill_mark`): đi từ **`v_start = bed_vel`** lên **`v_end = target_vel`** (tức `46 → 64` hoặc `54 → 64` khi giường là `p`; `62 → 80` hoặc `68 → 80` khi giường là `mp`).
           - Với `direction == "fall"` (`Lắng` — mở ở `fill_mark` rồi `<diminuendo>` hạ hơn nửa bậc, vẫn đứng trên giường): đi từ **`v_start = target_vel`** xuống **`v_end = 56 if fill_mark == "mp" else 72`** (tức `64 → 56` trên giường `p`, hoặc `80 → 72` trên giường `mp`).
           - Nốt thứ `k` (`0 <= k < m_b`) trong `sub_group` nhận:
             ```python
             vel_k = round(v_start + (v_end - v_start) * k / (m_b - 1))
             ```
4. **Dựng `comp_dynamics` theo từng ô và từng phách**:
   - Duyệt `bar` từ `0` đến `musical_bars - 1`, theo dõi `current_comp_mark: str | None = None`:
     - Tại `beat = 0.0`: nếu ô `bar` có ít nhất một nốt kêu tại `beat == 0.0` (guide tone ở khuông 1 hoặc root ở khuông 2) và `bed_marking_at[bar] != current_comp_mark`:
       - Thêm `DynamicEvent(bar=bar, marking=bed_marking_at[bar], sound=SOUND[bed_marking_at[bar]], beat=0.0)`.
       - Cập nhật `current_comp_mark = bed_marking_at[bar]`.
     - Tại mỗi sự kiện fill `(b, fill_beat, start_mark, has_wedge)` trong ô `bar`:
       - Nếu `start_mark != current_comp_mark`:
         - Thêm `DynamicEvent(bar=bar, marking=start_mark, sound=SOUND[start_mark], beat=fill_beat)`.
       - Cập nhật `current_comp_mark = "drifted" if has_wedge else start_mark` (để sau bất kỳ fill nào có `<wedge>` hoặc đổi chữ, hợp âm đệm ở `beat = 0.0` của ô kế tiếp luôn in lại chữ giường!).

### C. Thứ tự ghi XML trong `_piano_part` và thuật toán cắt biên trong `daily_frame.py` & `movement_frame.py`

1. **Thứ tự ghi XML trong `_piano_part` (`backend/app/sonify/musicxml.py`)**:
   - Khi `score.variant == "symphony"`:
     - Lấy `comp_open, comp_rest = _opening_dynamic(score.comp_dynamics, PIANO_DYNAMIC)`.
     - Tại `bar == 0`, in `_dynamic(measure, comp_open)` ngay sau `_attributes(...)` (trước vòng lặp `for event in symbols[bar]: _harmony(...)`).
     - Với `bar > 0`, các sự kiện trong `comp_rest` của ô `bar` có `beat == 0.0` được in **trước vòng lặp `symbols[bar]`**.
     - Các sự kiện `comp_rest` có `beat > 0.0` và `score.comp_wedges` của ô `bar` được trộn theo `_direction_order` và xả bằng `flush(event.beat)` bên trong vòng lặp `staff == 1` (và `flush(score.bar_beats)` ở cuối `staff == 1`).
2. **`_curtain_comp` trong `movement_frame.py` (Khung động của Giao hưởng)**:
   - Chỉ gán `velocity = 49` trên danh sách `notes` của warm-up / `tag_bars` **trước khi gọi `with_rests(notes, ...)`** bên trong `_curtain_comp` (tuyệt đối không chạm vào `*_kept_comp(score.comp, body, cool)`).
3. **Cắt và mở lại `high_wedges`, `high_dynamics`, `comp_wedges`, `comp_dynamics` tại biên khung (`daily_frame.py` & `movement_frame.py`)**:
   - **Hàm `_trim_frame_wedges(wedges, body, cool, beats, eighths_per_bar)` (dùng cho `high_wedges` và `comp_wedges`)**:
     - Ghép từng cặp `(start_w, stop_w)` liên tiếp trong `wedges`:
       - Nếu `stop_w` kết thúc tại hoặc trước `(body, 0.0)` (`stop_w.bar < body` hoặc `(stop_w.bar == body and stop_w.beat <= 0.0)`), hoặc `start_w.bar >= cool`: loại bỏ cả cặp.
       - Nếu `start_w.bar < body` nhưng `stop_w` nằm sau `(body, 0.0)` (câu bắt đầu từ vùng warm-up nhưng đỉnh/kết thúc vẫn nằm trong thân bài `[body, cool)`): **mở lại `start_w` tại `(bar=body, beat=0.0)`** (`start_w = WedgeEvent(body, 0.0, start_w.kind)`).
       - Nếu `stop_w.bar >= cool`: cắt `stop_w` về cuối thân bài `WedgeEvent(cool - 1, beats, "stop")`.
       - Chỉ giữ cặp `(start_w, stop_w)` nếu khoảng cách giữa chúng sau khi cắt vẫn đạt ít nhất `WEDGE_MIN` (`1.0` phách đen = 2 móc đơn).
   - **Hàm `_flute_body_dynamics(events, notes, body, cool)`**:
     - Tách riêng bước **khôi phục chữ `"mf"` đang có hiệu lực tại `(body, 0.0)`** và bước **xóa chữ `"mp"` thừa tại đúng `(body, 0.0)`** (tuyệt đối không xóa chữ `"mp"` ở `bar > body` hoặc `beat > 0.0`, vì đó là chữ reset sau một `<wedge>` trong thân bài!):
       ```python
       before = [e.marking for e in events if e.bar < body or (e.bar == body and e.beat == 0.0)]
       body_mark = before[-1] if before else "mp"
       kept = [e for e in events if body <= e.bar < cool]
       # 1) Chỉ bỏ phần tử đầu nếu nó nằm ngay tại (body, 0.0) và trùng với "mp" mở đầu ở bar 0:
       if kept and kept[0].bar == body and kept[0].beat == 0.0 and kept[0].marking == "mp":
           kept = kept[1:]
       # 2) Nếu mức hiệu lực lúc bước vào (body, 0.0) đang là "mf" và Flute có nốt kêu tại (body, 0.0),
       #    đảm bảo (body, 0.0) có chữ "mf" (ngay cả khi phía sau trong kept có chữ "mp" ở phách/ô khác):
       has_body_note = any(n.bar == body and n.beat == 0.0 and n.midi is not None for n in notes)
       if (
           body_mark == "mf"
           and has_body_note
           and not (kept and kept[0].bar == body and kept[0].beat == 0.0)
       ):
           kept.insert(0, DynamicEvent(bar=body, marking="mf", sound=SOUND["mf"], beat=0.0))
       ```
   - **Hàm `_piano_frame_dynamics` cho `comp_dynamics`**:
     - Suy chữ giường tại ô `body` từ sự kiện giường (`beat == 0.0`) gần nhất tại hoặc trước `body`:
       ```python
       bed_before = [e.marking for e in score.comp_dynamics if e.bar <= body and e.beat == 0.0]
       body_mark = bed_before[-1] if bed_before else "p"
       kept = [e for e in score.comp_dynamics if body <= e.bar < cool]
       ```
     - **Khung tĩnh**: Đầu bài (`bar == 0`) đã là `"p"`. Nếu `kept` có phần tử đầu tại `(bar == body, beat == 0.0)` với `marking == "p"` thì bỏ phần tử đó; nếu `kept` chưa có phần tử tại `(bar == body, beat == 0.0)` và `body_mark != "p"` thì chèn `DynamicEvent(bar=body, marking=body_mark, sound=SOUND[body_mark], beat=0.0)` vào đầu `kept`.
     - **Khung động**: Mở đầu bằng `DynamicEvent(bar=warm_start, marking="p", sound=SOUND["p"], beat=0.0)`, xử lý biên `(bar == body, beat == 0.0)` giống khung tĩnh, nối `kept`. Nếu `tag > 0` thì nối thêm `DynamicEvent(bar=cool, marking="p", sound=SOUND["p"], beat=0.0)` khi chữ cuối khác `"p"`, hoặc khi chữ cuối vẫn là `"p"` nhưng một nêm `crescendo` bắt đầu tại hoặc sau chữ đó và `start.bar < cool`. Fill `Nở` trên giường `p` không in chữ mới; nêm nằm trọn trong ô nên tag vẫn được kéo về `p`. Khung nhận `comp_wedges` đã cắt biên.

---

## 6. Ma trận Cân bằng Âm lượng đầy đủ cho 12 Bộ Nhạc cụ (`_VOICE_VOLUME_DB`)

### A. Quy trình đo tái lập và Kiểm tra Peak từ `0.0s` (gồm cả Transient nhóm gõ)

Mọi con số RMS và Peak dBFS dưới đây được đo trên MuseScore 4.7.5 (`macOS`, thư viện MuseSounds `state = 1`) với fixture 6 ô nhịp `4/4` ở `120 BPM` (`2.0 giây/ô`), hòa âm `Cmaj7`:
- **Cửa sổ đo**: Lấy từ **`0.0s` đến `1.8s`** của từng ô `[b * 2.0, b * 2.0 + 1.8]` để bắt trọn cú gõ đầu tiên (attack transient) của các nhạc cụ gõ và dây gảy (`Glockenspiel`, `Crotales`, `Marimba`, `Harp`, `Acoustic Steel Plucked`).
- **Kiểm tra Headroom / Chống Clipping từ `0.0s`**:
  - `Glockenspiel` (`symphony brass` P5): Peak gốc từ `0.0s` là **`-40.0 dBFS`** $\rightarrow$ cộng `+10 dB` thành **`-30.0 dBFS`**.
  - `Crotales` (`minimalist mallet` P5): Peak gốc từ `0.0s` là **`-36.5 dBFS`** $\rightarrow$ cộng `+12 dB` thành **`-24.5 dBFS`**.
  - `Marimba` (`minimalist mallet` P1): Peak gốc từ `0.0s` là **`-38.6 dBFS`** $\rightarrow$ cộng `+10 dB` thành **`-28.6 dBFS`**.
  - `Harp` (`symphony wood` P3): Peak gốc từ `0.0s` là **`-34.5 dBFS`** $\rightarrow$ cộng `+8 dB` thành **`-26.5 dBFS`**.
  - Lưu ý về đặc tính âm học của `Glockenspiel` và `Crotales`: đây là các nhạc cụ chuông kim loại có sóng âm tắt nhanh sau cú gõ nên trị số RMS trung bình trên cả ô 2 giây thấp hơn kèn/marimba, nhưng **Peak transient ở đầu phách sau khi cộng `+10 / +12 dB` đạt `-30.0 dBFS` đến `-24.5 dBFS`**, ngang bằng với Peak của `Trumpet` (`-29.2 dBFS`) và `Marimba` (`-28.6 dBFS`), giúp tiếng chuông xuyên qua bản phối rất rõ mà vẫn còn hơn `24 dB` headroom chống clip.

### B. Cơ chế phân biệt `French Horns a6` (`symphony brass`) và `French Horn` (`ambient classic`)

Trong `backend/app/sonify/audio.py` (dòng 581–598 và 674–679), `_assign_installed_sounds` tra giọng MuseSounds theo thứ tự: đầu tiên kiểm tra `named = requested[index]` từ `_xml_part_sounds(xml_path)` (khớp `<part-name>` hoặc `<instrument-name>` với khóa của `_VOICE_BY_SOUND`), nếu không khớp (`named is None`) mới rơi về `_VOICE_BY_INSTRUMENT.get(kind)` theo `instrumentId` của MuseScore:
- Ở `("symphony", "brass")`: `ensemble.py` xuất `<part-name>French Horns a6</part-name>`, khớp trực tiếp với `_VOICE_BY_SOUND["French Horns a6"]` $\rightarrow$ gắn **`museName = "French Horns a6"` (`id = 96`)**.
- Ở `("ambient", "classic")`: `musicxml.py` xuất `<part-name>Swell</part-name>` và `<instrument-name>Horn in F</instrument-name>` (cả hai không nằm trong khóa `_VOICE_BY_SOUND`), nên `named` là `None` và fallback sang `_VOICE_BY_INSTRUMENT["brass.french-horn"]` $\rightarrow$ gắn **`museName = "French Horn"` (`id = 108`)**.
Hai giọng này hoàn toàn tách biệt nhau trong `audiosettings.json`, nên khóa `"French Horns a6": -5` chỉ hạ dàn 6 kèn cor của Giao hưởng Đồng mà giữ nguyên `French Horn` đơn của Ambient ở `0 dB`.

### C. Bảng Ma trận toàn bộ 12 Bộ Nhạc cụ (60 vị trí = 4 Variants × 3 Ensembles × 5 Parts)

Đối với `Clarinet in Bb`: đặt **`Clarinet in Bb: +3 dB`**, kết hợp với **`Oboe: +6 dB`** (ở `symphony wood`) và **`Tenors: +2 dB`, `Violas: +3 dB`** (ở `ambient choir`). Khi đó:
- Ở `symphony wood`: `Oboe` (P1, `-43.2 + 6 = -37.2 dB`) đứng trên `Clarinet in Bb` (P2, `-41.2 + 3 = -38.2 dB`) đúng `1.0 dB`.
- Ở `ambient choir`: `Clarinet in Bb` (P1, `-46.4 + 3 = -43.4 dB`) đứng trên cả `Tenors` (P2, `-46.4 + 2 = -44.4 dB`) lẫn `Violas` (P3, `-47.7 + 3 = -44.7 dB`).

| Variant & Ensemble | `P5` Điểm cao | `P1` Giai điệu | `P2` Bè giữa | `P3` Hòa âm / Đệm *(sau `<play>0</play>`)* | `P4` Bass / Drone |
|---|---|---|---|---|---|
| **1. `symphony` · `classic`** | `Flute 1`<br>RMS `-47.9` $\rightarrow$ **`+5 dB`** | `Violins 1`<br>RMS `-38.1` $\rightarrow$ **`+2 dB`** | `Cellos`<br>RMS `-40.6` $\rightarrow$ **`+4 dB`** | `Piano`<br>RMS `-41.9` $\rightarrow$ **`-2 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **2. `symphony` · `wood`** | `Piccolo`<br>RMS `-34.6` $\rightarrow$ **`0 dB`** | `Oboe`<br>RMS `-43.2` $\rightarrow$ **`+6 dB`** | `Clarinet in Bb`<br>RMS `-41.2` $\rightarrow$ **`+3 dB`** | `Harp`<br>RMS `-52.4` $\rightarrow$ **`+8 dB`** | `Contrabassoon`<br>RMS `-49.5` $\rightarrow$ **`+10 dB`** |
| **3. `symphony` · `brass`** | `Glockenspiel`<br>Pk `-40.0` $\rightarrow$ **`+10 dB`** | `Trumpet`<br>RMS `-44.6` $\rightarrow$ **`+6 dB`** | `Trombone`<br>RMS `-50.2` $\rightarrow$ **`+8 dB`** | `French Horns a6`<br>RMS `-34.8` $\rightarrow$ **`-5 dB`** | `Tuba`<br>RMS `-32.2` $\rightarrow$ **`-5 dB`** |
| **4. `jazz` · `classic`** | `Vibraphone`<br>RMS `-41.6` $\rightarrow$ **`+3 dB`** | `Alto Saxophone`<br>RMS `-33.1` $\rightarrow$ **`0 dB`** | `Tenor Saxophone`<br>RMS `-35.9` $\rightarrow$ **`0 dB`** | `Suitcase Piano`<br>RMS `-35.1` $\rightarrow$ **`-2 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **5. `jazz` · `soul`** | `Electric LP - Clean`<br>RMS `-45.1` $\rightarrow$ **`+4 dB`** | `Trumpet`<br>RMS `-44.6` $\rightarrow$ **`+6 dB`** | `Trombone`<br>RMS `-50.2` $\rightarrow$ **`+8 dB`** | `Wurly 200A`<br>RMS `-39.7` $\rightarrow$ **`0 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **6. `jazz` · `organ`** | `Electric SC - Clean`<br>RMS `-42.4` $\rightarrow$ **`+4 dB`** | `Soprano Saxophone`<br>RMS `-31.8` $\rightarrow$ **`0 dB`** | `Baritone Saxophone`<br>RMS `-35.4` $\rightarrow$ **`0 dB`** | `Hammond Organ`<br>RMS `-42.2` $\rightarrow$ **`0 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **7. `minimalist` · `classic`** *(MS Basic)* | `Synth Bell`<br>RMS `-29.1` $\rightarrow$ **`0 dB`** | `Synth Arpeggio`<br>RMS `-28.0` $\rightarrow$ **`0 dB`** | `Synth Pad`<br>RMS `-32.0` $\rightarrow$ **`0 dB`** | `Synth Pulse`<br>RMS `-35.8` $\rightarrow$ **`0 dB`** | `Sub-Bass`<br>RMS `-28.0` $\rightarrow$ **`0 dB`** |
| **8. `minimalist` · `mallet`** | `Crotales`<br>Pk `-36.5` $\rightarrow$ **`+12 dB`** | `Marimba`<br>Pk `-38.6` $\rightarrow$ **`+10 dB`** | `Full Choir`<br>RMS `-50.9` $\rightarrow$ **`+8 dB`** | `Harpsichord`<br>RMS `-41.0` $\rightarrow$ **`0 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **9. `minimalist` · `guitar`** | `Flute 2`<br>RMS `-34.6` $\rightarrow$ **`0 dB`** | `Acoustic Steel Plucked`<br>RMS `-47.6` $\rightarrow$ **`+8 dB`** | `Cellos`<br>RMS `-40.8` $\rightarrow$ **`+4 dB`** | `Upright Piano`<br>RMS `-44.6` $\rightarrow$ **`0 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **10. `ambient` · `classic`** | `Celesta`<br>RMS `-37.7` $\rightarrow$ **`+6 dB`** | `Alto Flute`<br>RMS `-39.3` $\rightarrow$ **`0 dB`** | `Bass Flute`<br>RMS `-40.4` $\rightarrow$ **`-5 dB`** | `French Horn`<br>RMS `-40.8` $\rightarrow$ **`0 dB`** | `Contrabasses`<br>RMS `-32.7` $\rightarrow$ **`0 dB`** *(hạ từ `+4`)* |
| **11. `ambient` · `breath`** | `Handchimes`<br>RMS `-31.1` $\rightarrow$ **`0 dB`** | `English Horn`<br>RMS `-29.9` $\rightarrow$ **`0 dB`** | `Bass Clarinet`<br>RMS `-40.6` $\rightarrow$ **`0 dB`** | `Trombones a3`<br>RMS `-38.7` $\rightarrow$ **`0 dB`** | `Contrabassoon`<br>RMS `-50.7` $\rightarrow$ **`+10 dB`** |
| **12. `ambient` · `choir`** | `Handbells`<br>RMS `-29.2` $\rightarrow$ **`0 dB`** | `Clarinet in Bb`<br>RMS `-46.4` $\rightarrow$ **`+3 dB`** | `Tenors`<br>RMS `-46.4` $\rightarrow$ **`+2 dB`** | `Violas`<br>RMS `-47.7` $\rightarrow$ **`+3 dB`** | `Basses`<br>RMS `-40.0` $\rightarrow$ **`0 dB`** |

Hằng số từ điển trong `backend/app/sonify/audio.py`:
```python
_VOICE_VOLUME_DB: dict[str, float] = {
    "Flute 1": 5,
    "Glockenspiel": 10,
    "Crotales": 12,
    "Vibraphone": 3,
    "Electric LP - Clean": 4,
    "Electric SC - Clean": 4,
    "Celesta": 6,
    "Violins 1": 2,
    "Oboe": 6,
    "Trumpet": 6,
    "Clarinet in Bb": 3,
    "Marimba": 10,
    "Acoustic Steel Plucked": 8,
    "Cellos": 4,
    "Trombone": 8,
    "Full Choir": 8,
    "Tenors": 2,
    "Bass Flute": -5,
    "Piano": -2,
    "Harp": 8,
    "French Horns a6": -5,
    "Suitcase Piano": -2,
    "Violas": 3,
    "Electric Bass": -6,
    "Contrabassoon": 10,
    "Tuba": -5,
}
```

---

## 7. Danh mục thay đổi cụ thể trong Codebase

1. **`backend/app/sonify/model.py`**:
   - Thêm 4 trường có giá trị mặc định `()` trên `Score`:
     - `high_wedges: tuple[WedgeEvent, ...] = ()`
     - `high_dynamics: tuple[DynamicEvent, ...] = ()`
     - `comp_wedges: tuple[WedgeEvent, ...] = ()`
     - `comp_dynamics: tuple[DynamicEvent, ...] = ()`
   - Thêm 4 `@property` tương thích ngược: `flute_wedges`, `flute_dynamics`, `piano_wedges`, `piano_dynamics`.
2. **`backend/app/sonify/dynamics.py`**:
   - Thêm `PIANO_VELOCITY: dict[str, int] = {"p": 46, "mp": 54, "mf": 62, "f": 68}`.
   - Thêm `effective_comp_band(band: str, bar: int | None = None) -> str` (hạ band qua `groove.chamber`, `groove.trio_thin`, `groove.half`).
   - Thêm `piano_marking(band: str) -> str` (`"p"` khi `band in ("p", "mp")`, `"mp"` khi `band in ("mf", "f")`).
3. **`backend/app/sonify/phrasing.py`**:
   - Mở rộng `left_hand(slot, *, velocity_at=None, every_bar_at=frozenset())` để nhận velocity giường và tập các ô đánh gốc mỗi ô. `every_bar_at` được xét trước nhánh outro, nên ô `f` hoặc `rally` trong slot outro vẫn đánh lại gốc. Lời gọi `left_hand(slot)` của `jazz.py` không truyền tập đó và giữ pedal outro một lần.
4. **`backend/app/sonify/render.py`**:
   - `_flute_and_violin_dovetail`: thêm tham số `ensemble: Ensemble = "classic"`, trả về `(flute_notes, yield_spans, flute_wedges, flute_dynamics)` theo đúng state machine và bảng chuyển trạng thái ở Mục 3.
   - `_bass_pattern` / `_bass_bar`: thêm tham số `under_cello: bool = False`, chỉ bật khi ô đó nằm trong `cello_lead_bars` (Cello kêu $\ge \max(\text{quarter\_beats}/2, 2.0)$ phách đen), hạ bước `OCTAVE` về `ROOT` và gập mọi nốt Bass `>= 48` (`Đô3`) xuống dưới `48`.
   - `_right_hand`: nhận thêm `bed_velocity_at`, `bed_marking_at`, `phrases=None` (coi như `()`), trả về `(comp_notes, fill_marks, comp_wedges)` với `<wedge>` ngắn và nội suy velocity theo từng `sub_group` trên mỗi ô nhịp `b` đúng như Mục 5B.
   - Trong nhánh `symphony` của `_compose`: tính `eff_bands`, `bed_velocity_at`, `bed_marking_at`, `dense_left_bars`, dựng `comp_dynamics` cùng `comp_wedges` và gán vào `Score`.
5. **`backend/app/sonify/musicxml.py`**:
   - Giữ nguyên `_opening_p` cho `P1` và `P2`. Thêm `_opening_dynamic(dynamics, default)` chỉ dùng cho `P5` và `P3` của Giao hưởng.
   - `score_to_musicxml`: khi `score.variant == "symphony"`, lấy `high_open, high_rest = _opening_dynamic(score.high_dynamics, MELODY_DYNAMIC)` và truyền `score.high_wedges`, `high_rest`, `opening_dynamic=high_open` vào `_melody_part` của `P5`.
   - `_piano_part`: khi `score.variant == "symphony"`, lấy `comp_open, comp_rest = _opening_dynamic(score.comp_dynamics, PIANO_DYNAMIC)`, in `comp_open` ở `bar == 0` và các sự kiện `comp_rest` tại `beat == 0.0` trước vòng lặp `symbols[bar]`, rồi xả các sự kiện `comp_rest` tại `beat > 0.0` cùng `score.comp_wedges` theo `flush(event.beat)` trong vòng lặp `staff == 1`.
6. **`backend/app/sonify/span.py`, `movement_frame.py`, `daily_frame.py`**:
   - `slice_score`: dịch `high_wedges`, `high_dynamics`, `comp_wedges`, `comp_dynamics`.
   - `apply_span_frame` & `apply_daily_frame`: cắt và mở lại `high_wedges`, `comp_wedges` tại biên `body` qua `_trim_frame_wedges`, cắt/khôi phục `high_dynamics`, `comp_dynamics` theo đúng thuật toán ở Mục 5C; gán `velocity = 49` chỉ cho các nốt có cao độ do `_curtain_comp` sinh ra ở warm-up / `tag_bars` (trước `with_rests`, không chạm vào `_kept_comp`).
7. **`backend/app/sonify/audio.py`**:
   - Thêm `_VOICE_VOLUME_DB` và `_mute_mscx_harmony(mscx_bytes)` (thay thế regex không phá định dạng XML gốc của `score.mscx`) vào `_assign_installed_sounds`.
   - Tăng `RECAP_REVISION` từ `"28"` lên **`"29"`**, và `SPAN_REVISION` từ `"14"` lên **`"15"`**.
8. **`backend/tests/test_harmony.py`, `test_sonify_plan.py`, `test_daily_frame.py`, `test_recap.py`**:
   - Cập nhật `test_chamber_bar_drops_the_symphony_right_hand` trong `test_sonify_plan.py` (dòng 928) mở tuple `notes, *_ = _right_hand(...)`.
   - Trong `test_harmony.py`, cập nhật đầy đủ 4 nhóm assertion Piano/velocity hiện hữu bị ảnh hưởng (`test_phrase_regime_uses_the_downbeat_window`, `test_musicxml_writes_harmony_and_letter_dynamics` & `_assert_measure_timing`, `test_piano_answers_a_held_cadence_under_the_violin`, `test_fills_stay_in_the_cadence_tail_on_chord_tones`).
   - Chạy toàn bộ test suite (`pytest`) và bổ sung đầy đủ các bài test mới ở Mục 8.

---

## 8. Tiêu chí Kiểm tra (Test Plan)

- **Flute (`P5`)**:
  - Khi `peak == 72` (thanh khoản tại đỉnh là `p`/`mp` và không có `BREAKOUT`), Flute giữ chữ `"mp"` phẳng và **không sinh `<wedge>`** (velocity vuốt nhẹ trong `64..72`).
  - Khi `peak == 80` (thanh khoản tại đỉnh là `mf`/`f` hoặc có `BREAKOUT`) và `phrase.rise >= MIN_RISE`:
    - Đoạn 1 nốt sáo ngân dài duy nhất ($\ge 4$ móc, Hình thái 2 — ưu tiên trước Hình thái 1) sinh cặp `< >` với đỉnh ở giữa ngân (`mid_apex`), không in chữ `mf` ở giữa đoạn.
    - Đoạn leo lên đỉnh (`span_apex - arc_start >= WEDGE_MIN`, Hình thái 1) có đỉnh hairpin trùng móc giá gốc cao nhất đầu tiên (`span_apex` từ `pitches`), kể cả khi `flute_harmony_pitch` đã gập nốt đó xuống một quãng tám.
    - Khi Flute vào ngay tại đỉnh (`span_apex - arc_start < WEDGE_MIN`, Hình thái 3, `ensemble != "brass"`), `P5` mở chữ `mf` tại `arc_start` kèm `diminuendo`, rồi in lại `mp` ở tiếng đánh mới kế tiếp (nếu rơi vào `(bar=0, beat=0.0)`, ô 1 chỉ in đúng một thẻ `<dynamics><mf/></dynamics>`).
  - **Chuyển trạng thái sau `crescendo` trần (Trường hợp 4a)**: Đoạn Flute kết thúc ngay tại đỉnh (`sounding_end - span_apex < WEDGE_MIN`, chỉ có `crescendo`) đặt `effective_level = "drifted"`; đoạn Flute kế tiếp luôn in tường minh `start_marking` của nó (`"mp"` hoặc `"mf"`).
  - **Đoạn có nốt đầu buộc nối qua ranh giới phrase (`tie_first_in == True`)** và **giao khoảng `BREAKOUT`**: Không đặt chữ/wedge trên nốt nối dây (`r_i == 0`), và `f_run` giao với run `BREAKOUT` của `phrase.runs` nhận đúng `vel = 80`.
  - `ensemble == "brass"` (`Glockenspiel`): đoạn 1 run không sinh `<wedge>` (chỉ in `mf` khi `peak == 80` và `rise >= MIN_RISE`); đoạn $\ge 2$ runs ở `peak == 80` có `<wedge>` và không bao giờ bị kích chữ `"mf"` ở cả Hình thái 1, 2 lẫn 3.
- **Violin (`P1`), Cello (`P2`) & Bass (`P4`)**:
  - `lead_wedges` và `support_wedges` giữ nguyên hành vi hiện tại (pass toàn bộ test trong `test_harmony.py`).
  - Khi Cello hát chính ở ô `bar` (tổng thời lượng nốt Cello $\ge \max(\text{quarter\_beats}/2, 2.0)$ phách đen), toàn bộ nốt Bass trong ô đó (kể cả bậc 5 của các hợp âm `F..B`) đều có `midi < 48` (`Đô3`). Các ô chỉ có nốt dovetail ngắn (`< 2.0` phách đen, bao gồm đoạn 3 móc ở `6/8`) giữ nguyên pattern Bass hiện tại.
- **Piano (`P3`) & Frame (`daily_frame`, `movement_frame`)**:
  - Giường chỉ in `p` và `mp` theo `effective_comp_band`, đứng trước `<harmony>` tại `beat == 0.0`. Velocity giường nhận đúng `46 / 54 / 62 / 68`.
  - Ô `f` (sau groove) hoặc `groove.rally` đánh gốc tay trái mỗi ô trên Giao hưởng, kể cả khi ô đó nằm trong slot `outro`. `left_hand` của Jazz giữ nguyên đánh mỗi 2 ô và outro chỉ đánh một lần. Kiểm tra XML sau `render` chỉ còn thấy band `f` trên `liquidity`, vì groove đã được xóa khi `render` trả về; ô `rally` được kiểm tra khi ngữ cảnh groove còn mở.
  - Trên mỗi `sub_group` của câu fill: hướng `Nở` ($\ge 2$ nốt) giữ nguyên chữ giường, mở `<crescendo>` và nội suy velocity từ `bed_velocity_at[b]` lên `target_vel` (`46/54 → 64` hoặc `62/68 → 80`); hướng `Lắng` ($\ge 2$ nốt) in `fill_mark` (+1 bậc), mở `<diminuendo>` và nội suy velocity từ `target_vel` xuống `56` hoặc `72`; hướng `Ngang` hoặc 1 nốt in `fill_mark` (`64` hoặc `80`) không kèm `<wedge>`. Hợp âm đệm kế tiếp in lại chữ giường ở `beat = 0.0`.
  - **Cắt/nối qua Frame**: Nốt do `_curtain_comp` sinh ở warm-up / `tag_bars` có `velocity = 49` (không chạm `_kept_comp`). Khi một `<wedge>` của Flute mở trước `body` nhưng kết thúc sau `(body, 0.0)` với độ dài còn lại $\ge \text{WEDGE\_MIN}$, `_trim_frame_wedges` mở lại cạnh wedge tại `(bar=body, beat=0.0)`. Khi mức hiệu lực tại `(body, 0.0)` là `"mf"` trên Flute (kể cả khi phía sau trong thân bài có chữ `"mp"` ở phách/ô khác) hoặc `"mp"` trên Piano, khung khôi phục đúng chữ đó tại `(bar=body, beat=0.0)` mà không làm mất chữ `"mp"` reset phía sau.
- **Audio & `<Harmony>` (`audio.py`)**:
  - Unit test với fixture `.mscz` xác nhận `_mute_mscx_harmony` chèn `<play>0</play>` (idempotent, giữ nguyên phần còn lại của `score.mscx`) và gắn đúng `volumeDb` từ `_VOICE_VOLUME_DB`, kèm smoke test tích hợp qua `musescore_export` (tự động `pytest.skip` khi không có binary MuseScore) kiểm tra cả xuất WAV thành công lẫn độ giảm RMS (~6 dB) khi tắt Piano ẩn của `<Harmony>`.
