# Giọng gốc, chuyển giọng và bản sắc hợp âm theo cổ phiếu & chương

Kế hoạch bước tiếp theo sau `docs/sonify-long-form.md`: mở rộng hệ thống từ một giọng cố định (`C major / A minor`) sang **6 vùng giọng trên vòng quãng 5**, cho phép **chuyển giọng (modulation) Trưởng ↔ Thứ / Át / Hạ Át giữa các chương**, và **điều phối màu sắc hòa âm theo tính chất cổ phiếu cũng như nội dung từng chương**.

---

## 1. Nguyên tắc cốt lõi: Soạn trên bậc âm (Roman Numerals), xuất theo Giọng (`KeySpec`)

Toàn bộ engine hiện tại (`form.py`, `phrasing.py`, `jazz.py`, `minimalist.py`, `render.py`) đang giải bài toán hòa âm và giai điệu trên **thang 7 bậc diatonic + 12 hợp âm mượn** lấy `C` (`MIDI 60`) làm bậc `I` và `A` (`MIDI 57`) làm bậc `vi`.

Để đổi giọng gốc mà **không phải viết lại** Markov Viterbi, quy tắc dovetail Violin/Cello/Flute, hay DP tầm cữ của Alto/Tenor Sax:

1. **Mọi phép tính nội bộ giữ nguyên trên hệ quy chiếu bậc `I = C` (`fifths = 0`)**:
   - Bậc thang âm, khoảng cách semitone, và ma trận chuyển tiếp `TRANSITIONS` + `_BORROWED_EDGES` là bất biến đối với phép dịch giọng (transposition-invariant).
2. **Dịch giọng (`semitone_shift`) trong phạm vi hẹp `[-3, +2]` bán âm ở bước xuất `Score` / `MusicXML`**:
   - Dịch không quá 3 bán âm giúp mọi nhạc cụ (`Flute <= E6`, `Violin G3–C6`, `Cello C2–C4`, `Alto Sax G3–A♭5`, `Bass E1–C4`) vẫn nằm trọn trong vùng âm sắc ngọt nhất (sweet spot), không bị chói ở quãng cao hay đục ở quãng trầm.
3. **Chính tả nốt (`step`, `alter`) và ký hiệu hợp âm (`<harmony>`) dịch theo vòng quãng 5 (`fifths`)**:
   - Khuông nhạc khai báo `<fifths>` từ `-3` đến `+2`.
   - Mọi hợp âm trong `CHORDS` và `BORROWED` được dịch tên gốc theo bậc diatonic + dấu hóa tương ứng của giọng đích (ví dụ ở `F major` (`fifths = -1`): bậc `I` là `F`, bậc `IV` là `B♭`, bậc `vi` là `Dm`, hợp âm mượn `iv` là `B♭m`, `♭VI` là `D♭`, `V/V` là `G7`).

---

## 2. Bộ 6 vùng giọng chuẩn (`KeySpec`)

Sáu vùng giọng nằm quanh đỉnh vòng quãng 5, mỗi vùng gồm **một giọng Trưởng (bậc `I`)** và **giọng Thứ song song (bậc `vi`)**, kèm khả năng mượn sang **giọng Thứ cùng chủ âm (Parallel Minor — lùi 3 nấc `fifths`)**:

| Mã giọng (`key`) | Giọng Trưởng (`uptrend` / `sideway`) | Giọng Thứ song song (`downtrend`) | Giọng Thứ cùng chủ âm (Parallel Minor) | `fifths` | `semitones` (so với C) | Đặc tính âm sắc |
|---|---|---|---|---|---|---|
| `C` | C Major | A minor | C minor (`fifths = -3`) | `0` | `0` | Trong sáng, trung tính, cân bằng |
| `G` | G Major | E minor | G minor (`fifths = -2`) | `+1` (1♯) | `+2` *(hoặc `-5` ở bass)* | Sáng, vang, giàu bồi âm dây buông Violin/Cello |
| `D` | D Major | B minor | D minor (`fifths = -1`) | `+2` (2♯) | `+2` | Rực rỡ, hào sảng, hợp nhịp tăng trưởng / bứt phá |
| `F` | F Major | D minor | F minor (`fifths = -4`) | `-1` (1♭) | `-1` | Trầm tĩnh, điềm đạm (Pastoral), vững chãi |
| `Bb` | B♭ Major | G minor | B♭ minor (`fifths = -5`) | `-2` (2♭) | `-2` | Ấm, dày, giọng sở trường của Saxophone & Rhodes |
| `Eb` | E♭ Major | C minor | E♭ minor | `-3` (3♭) | `-3` *(hoặc `+3`)* | Bề thế, kịch tính (Heroic khi Trưởng, sâu lắng khi Thứ) |

*Lưu ý về độ dịch `G Major`:* Để giai điệu không bị đẩy cao thêm +7 bán âm, `G` có thể dịch `-5` bán âm ở bè giai điệu hoặc dùng dịch chuyển quãng 5 trong cữ đàn, hoặc chọn cặp dịch nhỏ: `Eb (-3)`, `Bb (-2)`, `F (-1)`, `C (0)`, `D (+2)`, và `A (-3)` / `G (-5/+2)`. Trong bước đầu, ưu tiên độ dịch tuyệt đối `<= 3` bán âm:
- `Eb`: `-3` bán âm (`fifths = -3`)
- `Bb`: `-2` bán âm (`fifths = -2`)
- `F`: `-1` bán âm (`fifths = -1`)
- `C`: `0` bán âm (`fifths = 0`)
- `G`: `-5` bán âm cho bass / `+2` với quy ước cữ đàn, hoặc dùng `D` (`+2` bán âm, `fifths = +2`) và `A` (`-3` bán âm, `fifths = +3`).

---

## 3. Ánh xạ Giọng gốc (`Home Key`) theo tính chất cổ phiếu

Người dùng có thể để **`Auto`** (mặc định) hoặc chọn trực tiếp giọng trên UI (`Auto`, `C`, `G`, `D`, `F`, `B♭`, `E♭`).

Khi ở chế độ **`Auto`**, `home_key(symbol, bars)` chọn giọng gốc ổn định cho mã cổ phiếu dựa trên nhóm ngành / tính chất giao dịch:

| Nhóm cổ phiếu | Mã tiêu biểu | Giọng gốc (`Home Key`) | Lý do âm nhạc |
|---|---|---|---|
| **Ngân hàng & Tài chính trụ cột** | `VCB`, `BID`, `CTG`, `TCB`, `MBB`, `ACB`, `VPB` | **`F`** (`F Major / D minor`) hoặc **`Bb`** (`B♭ Major / G minor`) | Âm khu ấm, chững chạc; đặc biệt hợp tiếng kèn Sax và Piano trầm. |
| **Công nghệ, Bán lẻ & Tăng trưởng** | `FPT`, `MWG`, `DGW`, `FRT`, `PNJ`, `CTR` | **`D`** (`D Major / B minor`) hoặc **`G`** (`G Major / E minor`) | Nhánh dấu thăng (`♯`) làm dàn dây sáng, giàu năng lượng tiến tới. |
| **Thép, Bất động sản, Chứng khoán (Chu kỳ cao)** | `HPG`, `HSG`, `NKG`, `VIC`, `VHM`, `NVL`, `SSI`, `VND` | **`Eb`** (`E♭ Major / C minor`) | Biên độ cảm xúc rộng: khi tăng nghe hùng tráng (`E♭`), khi giảm rơi vào `C minor` đầy kịch tính. |
| **Tiêu dùng, Phòng thủ, Điện – Khí** | `VNM`, `MSN`, `SAB`, `GAS`, `POW`, `REE` | **`C`** (`C Major / A minor`) | Trong trẻo, ổn định, ít màu sắc cực đoan. |
| **Mã khác (ngoài bảng cố định)** | Các mã HOSE/HNX còn lại | Suy ra từ `hash(symbol)` kết hợp biên độ `rel_span` | Đảm bảo mỗi mã có một "chữ ký giọng" nhất quán, không bị đổi ngẫu nhiên giữa các lần bấm. |

---

## 4. Kịch bản chuyển giọng (Modulation) qua các chương

### 4.1. Bản `1D` và `1W` (Một chương liền mạch)
- Giữ **một `Home Key` duy nhất** cho cả bài.
- Sự chuyển hóa Trưởng ↔ Thứ diễn ra tự nhiên bên trong giọng đó thông qua `regime` của từng phrase (`uptrend` → chủ âm `I`, `downtrend` → chủ âm `vi` thứ + hợp âm mượn `iv`, `♭VI`, `V/vi`).

### 4.2. Bản `1M` (Sonata 4 chương: `I – II – III – IV`)
Lấy `K` là `Home Key` (có số dấu hóa `f = K.fifths`):

- **Chương I (Trình bày — 96 ô, 96 BPM):** Mở tại **`K`** (`fifths = f`).
- **Chương II (Chậm / Ballad — 72 ô, 72 BPM):**
  - Nếu tuần 2 **giảm điểm** (`close_end < close_start * 0.99`): chuyển sang **Parallel Minor** (`fifths = f - 3`, ví dụ `C Major → C minor / E♭`). Giai điệu trầm hẳn xuống.
  - Nếu tuần 2 **tăng hoặc đi ngang**: chuyển sang **Subdominant** (`fifths = f - 1`, ví dụ `C → F`, `D → G`) — màu sắc thư giãn kinh điển của chương II Sonata.
- **Chương III (Scherzo — 72 ô, 120 BPM):**
  - Đặt ở **Dominant** (`fifths = f + 1`) hoặc giữ ở nhánh Thứ của `K` nếu tuần 3 biến động mạnh, tạo đà căng (tension) trước chương kết.
- **Chương IV (Finale — 96 ô, 96 BPM):**
  - Quay về **`K`** (`fifths = f`).
  - **Luật đảo chiều cuối kỳ (Triumph / Tragedy):**
    - Nếu đầu tháng giảm sâu nhưng tuần cuối bứt phá mạnh (`uptrend`): khóa chủ âm chương IV ở **Trưởng (`I`)** với cadence sáng.
    - Nếu cả tháng tăng nhưng tuần cuối gãy xu hướng mạnh (`downtrend` > 3%): chuyển Finale sang **Parallel Minor (`fifths = f - 3`)** để kết thúc đúng thực tế thị trường.

### 4.3. Bản `3M` (Concerto 3 chương: `I – II – III`)
- **Chương I (Tháng 1):** `Home Key` (`K`).
- **Chương II (Tháng 2 — Chậm, 60 BPM):** Chuyển sang **Subdominant (`f - 1`)** nếu tháng 2 tích lũy/tăng, hoặc **Parallel Minor (`f - 3`)** nếu tháng 2 suy giảm.
- **Chương III (Tháng 3 — Finale, 108 BPM):** Trở về **`K`** (hoặc `Parallel Minor` của `K` nếu tháng cuối rơi vào downtrend sâu).

### 4.4. Bản `1Y` (Tổ khúc 4 mùa — tối đa 12 chương)
Mười hai tháng đi qua **4 vùng giọng theo 4 mùa** trên vòng quãng 5, mỗi mùa 3 tháng (`Mở – Giữa – Khép`):

| Mùa trong năm | Các tháng lịch | Vùng giọng cơ sở (so với `Home Key = f`) | Biến thiên theo nội dung tháng |
|---|---|---|---|
| **Mùa Xuân (Q1)** | Tháng 1, 2, 3 | **`f`** (`Home Key`) | Tháng tăng dùng nhánh Trưởng; tháng giảm dùng nhánh Thứ song song (`vi`). |
| **Mùa Hạ (Q2)** | Tháng 4, 5, 6 | **`f + 1`** (Sang hướng Át — sáng hơn 1 nấc `♯`) | Nếu cả quý 2 giảm điểm thì đi theo hướng ngược lại **`f - 1`**. |
| **Mùa Thu (Q3)** | Tháng 7, 8, 9 | **`f - 1`** (Sang hướng Hạ Át — dịu và trầm hơn 1 nấc `♭`) | Tháng giảm sâu (> 5%) mượn xuống **`f - 3`** (Parallel Minor). |
| **Mùa Đông (Q4)** | Tháng 10, 11, 12 | Tháng 10–11 ở **`f - 2`** hoặc **`f + 1`**, Tháng 12 (Finale) quay về **`f`** | Tháng 12 chốt lại toàn bộ hành trình năm tại `Home Key`. |

---

## 5. Bản sắc hợp âm theo nội dung chương (`MovementCharacter`)

Ngoài việc chọn giọng (`KeySpec`) và `regime` từng phrase, toàn bộ chương có một chỉ số tổng kết từ chuỗi `bars` của chính chương đó:
- `return_pct = (bars[-1].close - bars[0].close) / bars[0].close`
- `volatility = (max_close - min_close) / min_close`

Từ hai con số này, chương mang một trong 4 **Bản sắc hòa âm (`MovementCharacter`)** tác động trực tiếp lên `REGIME_BIAS` và trọng số hợp âm mượn trong `form.py`:

1. **`rally` (Tăng trưởng rõ rệt: `return_pct >= +2.5%`):**
   - Giảm nhẹ chi phí của Secondary Dominants (`D7 -> G`, `C7 -> F`, `A7 -> Dm`).
   - Ưu tiên mở và kết phrase trên hợp âm Trưởng (`I`, `IV`, `V7`), tạo lực đẩy hướng lên.
2. **`selloff` (Sụt giảm mạnh: `return_pct <= -2.5%`):**
   - Tăng ưu tiên cho chủ âm thứ (`Am`/`Am7`) và nhóm modal mixture (`Fm`, `A♭`, `Bm7♭5`, `E7`).
   - Ở cadence cuối phrase, ưu tiên kết về `vi` (`Am`) hoặc half-cadence trên `E7` thay vì về `C` trưởng.
3. **`volatile` (Giằng co biên độ lớn: `|return_pct| < 2.5%` nhưng `volatility >= 4%`):**
   - Mở rộng xác suất đi qua hợp âm giảm và nửa giảm (`F♯°7`, `Bm7♭5`), hợp âm bảy (`maj7`, `7`, `m7`) thắng thế so với hợp âm ba thuần (`SEVENTH_TENSION_COST` giảm về `0.0`).
4. **`calm` (Tích lũy / Đi ngang biên độ hẹp: `|return_pct| < 2.5%` và `volatility < 4%`):**
   - Tăng `SEVENTH_TENSION_COST` ở bản Giao hưởng để ưu tiên hợp âm ba trong trẻo (`C`, `F`, `Am`, `Dm`) và màu Mixolydian nhẹ (`B♭`, `Gm`).
   - Giảm tần suất đổi hợp âm 1 ô (`SINGLE_BAR_CHANGE_PENALTY` tăng nhẹ) để nhịp thở hòa âm chậm và tĩnh hơn.

---

## 6. Chỗ nối hòa âm giữa hai chương (`Pivot Chord Bonus`)

Khi chuyển từ Chương $k$ (ở giọng $K_k$) sang Chương $k+1$ (ở giọng $K_{k+1}$):
- Lấy tập pitch classes thực tế (sau khi đã cộng `K_k.semitones`) của hợp âm kết Chương $k$.
- Trong `plan_markov_chords()` của Chương $k+1$, tại `bar == 0` (intro) và ô đầu tiên của `phrase` đầu tiên:
  - Hợp âm ứng viên nào (sau khi cộng `K_{k+1}.semitones`) chia sẻ **ít nhất 1 hoặc 2 âm chung (common tones)** với hợp âm kết của Chương $k$ sẽ được hưởng `PIVOT_CHORD_BONUS = 0.20`.
- Kết quả: Dù đổi giọng sau khoảng nghỉ 4–8 giây, hợp âm mở màn của chương mới vẫn nối tiếp âm hưởng vừa tắt của chương trước (đúng kỹ thuật *common-tone modulation* trong âm nhạc cổ điển).

---

## 7. Thiết kế kỹ thuật & Các file cần chạm

### 7.1. Module mới `backend/app/sonify/keys.py`
- Định nghĩa `KeyName = Literal["C", "G", "D", "F", "Bb", "Eb"]` và `KeySpec(name, fifths, semitones)`.
- Hàm `transpose_chord(chord: Chord, key: KeySpec) -> Chord`: dịch `root_step`, `alter`, `pitches`, và bảng `tones` của `Chord` sang giọng `key`.
- Hàm `midi_to_spelled_pitch(midi: int, key: KeySpec, harmony: Chord | None) -> tuple[str, int, int]`: trả về `(step, alter, octave)` đúng với hóa biểu `key.fifths` để không viết nhầm dấu thăng/giáng (ví dụ trong `F Major`, nốt `MIDI 70` luôn viết là `B♭` thay vì `A♯`).
- Hàm `stock_home_key(symbol: str, bars: list[Bar]) -> KeySpec` và `plan_movement_keys(home: KeySpec, span: str, parts: list[list[Bar]]) -> tuple[KeySpec, ...]`.

### 7.2. Cập nhật `Score`, `FormSpec` và `PreparedMovement`
- `FormSpec` và `PreparedMovement` nhận thêm `key: KeySpec = C_KEY` và `character: MovementCharacter = "calm"`.
- `Score` lưu `key: KeySpec = C_KEY` (hoặc `fifths: int = 0`).
- Trong `render()`:
  - Trước khi trả `Score`, dịch các `NoteEvent.midi` (hoặc dịch tại `musicxml.py` + truyền `key` vào `Score`) theo `key.semitones` và dịch `HarmonyEvent.chord` qua `transpose_chord(chord, key)`.
- Trong `musicxml.py`:
  - `_attributes()` ghi `<fifths>{score.key.fifths}</fifths>` thay vì `"0"`.
  - `midi_to_pitch()` đọc `score.key` để chọn đúng chính tả theo hóa biểu.

### 7.3. Cache & API (`audio.py`, `schemas.py`, `SpanRecap.tsx`)
- `scale_fingerprint` của `PreparedMovement` nối thêm mã giọng (`f"{key.name}:{low:.2f}-{high:.2f}"`), hoặc tăng `SPAN_REVISION = "2"` và `RECAP_REVISION = "10"` khi bật giọng mới.
- `SpanMovementResponse` có thể trả thêm trường `keyLabel: str` (ví dụ `"F Trưởng"`, `"D Thứ"`) để hiển thị tinh tế cạnh nhãn chương trên UI (`"I · F Trưởng"`).
- Tuỳ chọn: thêm query `key: KeyName | Literal["auto"] = "auto"` nếu muốn cho người dùng tự chọn giọng trên giao diện.

---

## 8. Thứ tự triển khai (Từng bước nhỏ, kiểm thử độc lập)

1. **Bước 1 — `keys.py` & `musicxml.py`:**
   - Viết `KeySpec`, phép dịch `Chord` và `midi_to_pitch` theo `fifths`.
   - Test xuất MusicXML ở cả 6 giọng (`C`, `G`, `D`, `F`, `Bb`, `Eb`) với cả hợp âm thuận lẫn 12 hợp âm mượn, đảm bảo không có lỗi chính tả nốt và MuseScore đọc đúng hóa biểu.
2. **Bước 2 — `MovementCharacter` & `Pivot Chord Bonus` trong `form.py`:**
   - Thêm điều chỉnh bias theo 4 tính cách (`rally`, `selloff`, `volatile`, `calm`) và điểm thưởng nối hợp âm giữa hai chương.
3. **Bước 3 — Gắn `Home Key` theo cổ phiếu & kịch bản chuyển giọng `1M / 3M / 1Y` trong `span.py`:**
   - Áp dụng bảng ánh xạ ngành cho cổ phiếu và quy tắc chuyển giọng qua các chương / các mùa.
4. **Bước 4 — Hiển thị nhãn giọng trên UI (`SpanRecap.tsx` / `SessionRecap.tsx`):**
   - Hiển thị giọng của chương đang phát và (tuỳ chọn) chip đổi giọng gốc.
