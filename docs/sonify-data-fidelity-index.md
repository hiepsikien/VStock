# DFI — Data Fidelity Index (Chỉ số độ trung thực dữ liệu)

> **Trạng thái:** đã implement cho dataset giá + volume; calibration corpus ở Phase 7.
>
> **Mục tiêu:** đo xem một bản sonify phản ánh **dữ liệu nguồn** trung thực đến đâu, ở cấp **câu → chương → tác phẩm → thể loại/dàn nhạc**. Đây là chỉ số **độ trung thực dữ liệu**, không phải điểm hay/xấu của âm nhạc.
>
> **Tổng quát:** DFI không gắn với chứng khoán. Dataset đầu tiên là **giá (OHLC) + volume**; cùng công thức dùng được cho chuỗi dữ liệu khác (crypto, order book, nhiệt độ, lưu lượng, sentiment…) vì mọi thành phần đều đo quan hệ giữa **tín hiệu nguồn** và **tín hiệu đã sonify**.
>
> **Phạm vi:** replay trước (`1D`, `1W`, `1M`, `3M`, `1Y`). Live stream để sau.
>
> **Liên quan:** [`sonify-explain.md`](./sonify-explain.md), [`sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`sonify-guitar-bach-suite-plan.md`](./sonify-guitar-bach-suite-plan.md), [`sonify-ambient.md`](./sonify-ambient.md), [`musicalize-plan.md`](./musicalize-plan.md).

---

## 1. Vấn đề

Sonify nhận một chuỗi dữ liệu và biến nó thành âm nhạc. Với chứng khoán, chuỗi đó là **giá và volume**; với dataset khác, nó có thể là bất kỳ tín hiệu nào có thứ tự thời gian. Câu hỏi của DFI:

> Người nghe có nghe ra **dữ liệu nguồn** không, hay chỉ nghe thấy một bản nhạc?

Trong dataset chứng khoán, pipeline mã hoá **đường giá** bằng nhiều cách khác nhau:

- Giao hưởng và Jazz gần như **hát đúng đường giá** ở bè chính.
- Tối giản mã hoá giá bằng **cửa sổ đăng ký của arpeggio**, không phải một nốt.
- Ambient mã hoá bằng **anchor thưa + ngân dài**, nhiều chỗ cố ý không restate giá.
- Sáu dàn guitar là **sáu thuật toán viết khác nhau**, có hoa mỹ, chuyển bè, tremolo, thumb cantabile.

Vì vậy không thể lấy “nốt cao nhất đang kêu” làm đường giá. Ví dụ:

- Bach prelude đặt nốt giá ở **móc kép chẵn**; móc kép lẻ là bậc phụ. Lấy nốt cao nhất sẽ bắt nhầm bậc phụ.
- Torroba đặt nốt giá ở **phách mạnh**; láy không thay nốt giá.
- Villa `thumb_cantabile` chuyển đường giá xuống **bè trầm**.
- Minimalist mã hoá giá bằng **độ cao trung bình/cửa sổ của arpeggio**, không phải từng nốt.
- Ambient ngân dài qua nhiều biến động giá; đó là chủ ý, nhưng làm chart mờ.

DFI phải đo **đúng nốt/tín hiệu mà writer chủ định dùng để mang dữ liệu nguồn** (hiện tại: đường giá; volume đo ở cấp cửa sổ), không suy ra từ âm thanh.

---

## 2. Nguyên tắc thiết kế

1. **Một trục duy nhất:** 0–100, càng cao càng dễ nghe ra dữ liệu nguồn (giá + volume). Không cộng điểm “giàu nhạc tính”.
2. **Đo trên tín hiệu chủ định, không đo trên audio.** Guitar ghi `PriceTracePoint` qua `_TRACE_LINE`; các variant còn lại dựng trace trong `_attach_dfi_inputs` từ nốt chủ đích của writer. Xem sai lệch đã biết ở §9.1.
3. **Chuẩn hoá theo cơ hội.** Phiên đi ngang không bị trừ điểm oan; chỉ tính trên những chỗ dữ liệu thực sự có biến động.
4. **Bất biến với đăng ký.** Jazz nén quãng tám, guitar đổi bè, ambient fold glass. Vì vậy so sánh **hướng và biên độ trong từng câu**, không so cao độ tuyệt đối giữa các câu.
5. **Tách “độ phủ” khỏi “độ chính xác”.** Một bản có thể đúng khi có nốt, nhưng im quá nhiều; hoặc có nốt đều nhưng giữ nguyên khi giá chạy.
6. **Không dùng để xếp hạng thể loại.** Ambient thưa là bản sắc, không phải lỗi. UI phải nói rõ: “độ trung thực dữ liệu”, không phải “chất lượng”.
7. **Volume là một phần của cùng trục**, không phải trục thứ hai. Volume được đo ở cấp cửa sổ thanh khoản, bằng tương quan hạng với năng lượng thật của bản nhạc.

### 2.1. Tên gọi

| Nơi hiển thị | Giá trị |
|---|---|
| Tên chỉ số | **DFI — Data Fidelity Index** |
| Pill trong replay | `DFI 78` (thiếu số: `DFI —`; ít mẫu: `DFI ~78`) |
| Sheet | `Độ trung thực dữ liệu` |
| Field API / code | `dfi` (module `sonify/dfi.py`, service `services/dfi.py`) |

Không dùng “độ rõ đường giá” làm tên chỉ số: DFI đo cả volume và sẽ mở rộng cho dataset khác, không chỉ đường giá. Trong phần còn lại, “giá” là **tín hiệu nguồn của dataset chứng khoán**; với dataset khác, đọc “giá” thành “tín hiệu nguồn”.

---

## 3. Cách pipeline hiện tại mã hoá dữ liệu giá

### 3.1. Tín hiệu chung

Với dataset chứng khoán, tín hiệu nguồn gồm **đường giá** và **volume**. Trong `backend/app/sonify/render.py`:

1. Mỗi musical bar lấy một nhóm nến nguồn (`groups`).
2. Giá được resample thành `eighths_per_bar` điểm:
   ```python
   raw_pitches.append(
       scale[price_to_scale_index(close, session_low, session_high, len(scale))]
   )
   ```
3. `quantize_strong_beats(...)` kéo phách mạnh về hợp âm đang chạy, tạo `pitches`.
4. `plan_phrases(...)` cắt câu tại chỗ giá đứng.
5. Volume được gom theo `LIQUIDITY_WINDOWS` (hoặc `liquidity_windows_for(spec)`), xếp thành band `p–f` bằng `marking_for_volume(...)`.

`raw_pitches` là đường giá **trước** khi bị hợp âm bẻ; `pitches` là đường giá **sau** khi quantize. DFI nên đo trên cái tai nghe thấy, tức `pitches` hoặc nốt cuối cùng writer chọn, nhưng vẫn giữ `close` gốc để biết “giá đã đi đâu”.

### 3.2. Từng thể loại

| Thể loại | Nốt/tín hiệu mang giá | Ghi chú cho DFI |
|---|---|---|
| **Giao hưởng** | `lead` = violin, sinh từ `melody_parts(pitches, ...)` trong `phrasing.py`. Flute là quãng 3/5 ở trên, không phải giá. Cello có lúc lấy dòng trầm. | Lấy `lead`, không lấy `high` (flute) và không lấy nốt cao nhất của cả score. |
| **Jazz** | `lead` = alto sax, `_sax_melody_curve(...)` từ `pitches`, có thể dịch cả câu 0/12/24 semitone để vừa register. Vibraphone là đỉnh/điểm nhấn, không phải giá. | So trong từng câu; bỏ qua dịch octave ở biên câu. Không lấy nốt vibraphone. |
| **Tối giản** | Arpeggio synth: cửa sổ đăng ký, độ sáng, articulation, velocity lấy từ `raw_pitches`; pulse lấy volume. | Không so từng nốt. Ghi `register_center` mỗi bar (trung bình cửa sổ arpeggio) làm `pitch` của trace. |
| **Ambient** | Glass line: anchor ở đầu câu/bar, ngân dài, thở bằng breath; bed theo hợp âm và volume. | Chỉ so ở anchor/breath. Ngân dài qua biến động giá là mất fidelity có chủ ý; coverage và shape phải phản ánh. |
| **Guitar — Bach** | Bè cao; prelude: móc kép chẵn là giá, móc kép lẻ là bậc phụ. | Trace chỉ ghi móc kép chẵn. Không lấy nốt cao nhất. |
| **Guitar — Sor** | Giai điệu `lead`; `cantabile` có quãng 3/6 song song ở dưới; Grand Solo có scale phủ. | Trace ghi nốt giai điệu, không ghi nốt đệm quãng 3/6. |
| **Guitar — Barrios** | Tremolo: nốt melody trên cùng của cluster; preludio: canto; andante: đỉnh hợp âm; `thumb_cantabile`: **bè trầm**. | Trace phải đổi voice theo pattern. Không giả định giá luôn ở bè cao. |
| **Guitar — Villa-Lobos** | `villa_pattern`: melody; `chord_melody`: đỉnh hợp âm; `thumb_cantabile`: bè trầm; etude: melody. | Như Barrios; trace theo pattern của từng câu. |
| **Guitar — Brouwer** | Melody/lead theo pattern study, chord-melody. | Trace theo lead; scale overlay không thay nốt giá. |
| **Guitar — Torroba** | Nốt giá ở **phách mạnh** (`ctx.strong`), láy/ornament không thay nốt giá. | Trace chỉ ghi nốt phách mạnh. Đây là case dễ bị “nốt cao nhất” đánh lừa nhất. |

### 3.3. Dàn nhạc

- Các ensemble không phải guitar (`wood`, `brass`, `soul`, `organ`, `mallet`, `breath`, `choir`) chủ yếu đổi **âm sắc, register, lực**, không đổi thuật toán giá. DFI phải gần như không đổi so với `classic` (kỳ vọng lệch ≤ 3 điểm).
- Sáu ensemble guitar là sáu thuật toán viết. DFI được phép lệch rõ. Đây là chỗ UI so sánh có ý nghĩa nhất.

Nếu DFI của `wood` lệch `classic` quá nhiều, gần như chắc chắn trace đang bắt nhầm nốt, không phải “gỗ nghe khác”.

---

## 4. Định nghĩa DFI

DFI là một chỉ số **theo dataset**, không theo riêng chứng khoán. Với dataset giá, các thành phần `S/M/T/R` đo đường giá và `V` đo volume; với dataset khác, thay “giá” bằng tín hiệu nguồn tương ứng và giữ nguyên cách chấm.

### 4.1. Công thức

```text
DFI = 100 × (0.33·S + 0.21·M + 0.19·T + 0.17·R + 0.10·V) × C
```

> Công thức này thay bản 4 thành phần đã bàn trước đó (`0.35/0.25/0.20/0.20`) bằng cách thêm **Khối lượng** vào cùng một trục. Volume chỉ giữ 0.10 vì band đã được writer in vào density/velocity theo thiết kế, nên `V` thường bão hoà; 0.02 còn lại dồn vào **Cấu trúc**, thành phần ít chồng lấn nhất với Shape. Calibration ở Phase 7 sẽ xác nhận lại.

| Ký hiệu | Tên | Trọng số | Câu hỏi |
|---|---|---:|---|
| `S` | Hình dạng (Shape) | 0.33 | Trong một câu, giá lên thì nốt lên, giá xuống thì nốt xuống? |
| `M` | Chuyển động (Motion) | 0.21 | Giá đi biên độ lớn thì nốt cũng đi xa hơn? |
| `T` | Cấu trúc (Structure) | 0.19 | Đỉnh/đáy, độ rộng và hướng lớn của câu có khớp? |
| `R` | Độ phân giải (Resolution) | 0.17 | Biến động giá có sinh ra thay đổi nốt, và ngược lại? |
| `V` | Khối lượng (Volume) | 0.10 | Volume lớn có nghe thành dày/to hơn? |
| `C` | Độ phủ (Coverage) | × | Đường giá có mặt ở các bar nguồn khi giá thực sự chạy? |

Nếu **không có volume** (dataset không có volume, symbol thiếu dữ liệu, hoặc mọi cửa sổ đều 0), bỏ `V` và chuẩn hoá lại:

```text
DFI = 100 × (0.33·S + 0.21·M + 0.19·T + 0.17·R) / 0.90 × C
```

Nếu `S`, `M`, `T`, `R` không tính được vì quá ít cơ hội, trả `null`, không trả 0.

### 4.2. Trace — dữ liệu đầu vào

Đề xuất thêm vào `Score`:

```python
@dataclass(frozen=True)
class PriceTracePoint:
    bar: int                     # cùng hệ với NoteEvent
    beat: float                  # cùng hệ với NoteEvent (quarter-note beat)
    duration_beats: float        # để biết nốt có đang kêu trong bar nguồn hay không
    price: float                 # close nguồn mà điểm này muốn mã hoá
    pitch: float | None          # cao độ nghe được, hoặc centroid của cửa sổ
    role: Literal["attack", "hold", "anchor", "register", "rest"]
    weight: float = 1.0
    voice: str = "lead"          # lead / high / low / thumb / ...
    source_bar: int | None = None
```

Quy ước:

- Trace dùng `(bar, beat)` để khớp trực tiếp với `NoteEvent`; không dùng `eighth` làm khoá chính. Khi cần lưới phân tích, quy đổi bằng `eighth = round((bar * score.bar_beats + beat) * 2)`.
- `pitch` là **một số thực** vì minimalist dùng centroid cửa sổ, không phải MIDI của một nốt.
- `duration_beats` là bắt buộc: Coverage cần biết một nốt ngân có phủ bar nguồn hay không.
- `hold` nghĩa là nốt đang ngân và vẫn đang đại diện cho giá; nếu giá chạy mà `pitch` không đổi, đó là lỗi fidelity, không phải im lặng.
- `rest` nghĩa là không có tín hiệu giá; dùng cho coverage.
- `role="anchor"` cho ambient; `role="register"` cho minimalist.
- Trace được ghi **ngay trong writer**, không trích xuất lại từ `NoteEvent`.

Ngoài ra, dùng lại đúng ba thứ `_compose` đã tính inline trong `render.py:1076–1083`:

```python
windows: tuple[tuple[int, int], ...]   # (start_bar, length_bars)
window_volumes: list[float]            # average_liquidity(...)
bands: list[str]                       # marking_for_volume(...)
```

Không cần thêm dataclass `VolumeWindow`; nếu muốn gói lại thì phải ghi rõ đó là type **mới**, không phải API đang có.

Không cần thêm trace volume vào từng writer; năng lượng thật lấy từ `NoteEvent` của score.

### 4.3. Chuẩn hoá theo cơ hội

DFI dùng **hai lưới**, có chủ đích:

1. **Lưới phân tích** cho `S/M/T/R`: bám theo cách thể loại viết nốt.
   - Giao hưởng, Jazz, Guitar: **mỗi eighth**.
   - Tối giản: **mỗi bar** (hoặc nửa bar nếu arpeggio đổi giữa bar).
   - Ambient: **mỗi anchor/breath**, cộng các điểm `hold` để biết giá có được restate hay không.
2. **Lưới nguồn chung** cho `C`: **mỗi source bar** (nến nguồn), ánh xạ vào musical time qua `groups`. Không dùng số musical bar làm đơn vị chung, vì các variant có form/`musical_bars` khác nhau. Lưới source bar giống nhau cho mọi variant/ensemble, nên `C` so sánh chéo được. Xem §4.9.

Bỏ hoàn toàn các section `warmup`, `cooldown`, `intro`, `outro` khỏi tử số và mẫu số. Đó là khung, không phải dữ liệu nguồn.

Với mỗi bước trên lưới phân tích:

```text
ΔP_t = P_t − P_{t−1}
```

`εp` được tính **trong từng câu**, không dùng một ngưỡng toàn bản:

```text
εp_phrase = max(
    0.05 × (phrase_high − phrase_low),
    0.25 × median(|ΔP| trong câu),
    0.0005 × median(close)          # sàn tuyệt đối, khoảng 5 bps
)
```

- Dùng biên của **câu**, không dùng biên cả phiên: một câu calm trong phiên volatile không bị đánh giá bằng thước của cả phiên. Nếu câu có ít hơn 4 điểm, fallback về biên session.
- Sàn `0.0005 × median(close)` chặn trường hợp cả bản toàn bước rất nhỏ làm `εp` bò xuống và `n_moves` bị thổi phồng.
- `|ΔP_t| > εp_phrase`: cơ hội thật.
- `|ΔP_t| ≤ εp_phrase`: giá đứng; không bắt buộc nốt phải đổi.
- Sàn này là điểm calibration ở Phase 7; có thể chỉnh theo volatility của từng symbol.

`n_moves = số bước trên lưới phân tích có |ΔP_t| > εp_phrase`.

Nếu `n_moves < 4`, trả `null` với lý do `low_opportunity`; UI hiện `DFI —`. Đây là cách “không trừ điểm phiên đi ngang”: không có cơ hội thì không có điểm, thay vì cho 0 hoặc 100 giả.

### 4.4. Shape — Hình dạng

Mục tiêu: trong từng câu, thứ tự cao thấp của giá và của nốt phải khớp.

Với mỗi câu có `n ≥ 4` điểm và biên giá > `εp`:

```text
ρ_phrase = Spearman(P_t, pitch_t)   # trong câu, không qua biên câu
S_phrase = max(0, ρ_phrase)
```

- Dùng **Spearman**, không dùng Pearson, vì pipeline lượng tử hoá giá thành thang âm; quan hệ đơn điệu là đủ.
- `max(0, ρ)` vì tương quan âm là sai rõ ràng, không thưởng.
- Câu có 2–3 anchor (ambient): thay bằng tỷ lệ đồng hướng của các cặp liên tiếp, chuẩn hoá về 0–1; trọng số thấp hơn.
- `S = Σ(n_phrase × S_phrase) / Σ n_phrase`, chỉ trên các câu tính được.
- Nếu giá có biến thiên nhưng cao độ đứng yên, `S_phrase = 0`, **không bỏ câu**. Bỏ đi rồi chia lại trọng số sẽ thưởng cho việc giữ một nốt.

Không gộp tất cả các câu thành một tương quan lớn: jazz dịch octave và guitar đổi bè sẽ tạo nhảy giả ở biên câu.

### 4.5. Motion — Chuyển động

Mục tiêu: biên độ. Giá đi 1% thì nốt có thể đi 1 bậc; giá đi 5% thì nốt nên đi xa hơn.

Với các cặp liên tiếp trong cùng câu:

```text
x = |ΔP_t|
y = |pitch_t − pitch_{t−1}|

τ_phrase = Kendall tau-b(x, y)
M_phrase = max(0, τ_phrase)
```

- Dùng Kendall tau-b vì có nhiều tie (giá đứng, nốt lặp).
- Bỏ các cặp **không có gì đổi** (`|ΔP| ≤ εp` và `|Δpitch| = 0`): giá chỉ đổi ở biên source bar nên phần lớn bước eighth là (0, 0), và tau-b tính chúng là tie làm loãng tương quan thật (0.6 → 0.05). Cặp `hold` thật (`|ΔP| > εp`, `Δpitch = 0`) vẫn giữ và vẫn bị phạt.
- Câu có ít hơn 4 cặp hoặc mọi `x` bằng nhau: bỏ qua, không cho điểm.
- Nếu `x` có biến thiên nhưng mọi `y` bằng 0, `M_phrase = 0`, **không bỏ câu** (cùng lý do với Shape).
- `M` là trung bình có trọng số theo số cặp.

**Fallback cho ambient / trace thưa:** Motion vẫn dùng **tất cả** cặp, kể cả `hold`, vì ngân dài qua biến động giá là mất fidelity thật. Nếu câu có ít hơn 3 cặp mà `x` khác 0 (quá ít anchor để tính tương quan), Motion chuyển sang so **anchor-to-anchor** (bỏ các `hold` thuần) và đánh dấu `M` là `low-evidence`; nếu vẫn không đủ, `M = null` và trọng số được chia lại. Như vậy ambient vẫn bị phạt khi ngân dài qua giá chạy, nhưng không bị kéo về 0 chỉ vì cấu trúc tie.

Motion khác Shape: Shape hỏi “cùng hướng không”, Motion hỏi “mạnh/yếu có tương xứng không”. Một bản có thể đúng hướng nhưng mọi thay đổi đều thành một bậc, hoặc ngược lại. Ambient thưa sẽ thấp ở Motion **có chủ ý**; UI ghi “thưa có chủ ý” để không mâu thuẫn với số.

### 4.6. Structure — Cấu trúc

Mục tiêu: những thứ tai nghe nhớ được — đỉnh, đáy, độ rộng, hướng của cả câu.

Ba thành phần:

1. **Vị trí đỉnh/đáy trong câu (0.50)**
   ```text
   apex = 1 − min(1, |t_apex_price − t_apex_pitch| / max(1, n_phrase / 2))
   trough = 1 − min(1, |t_trough_price − t_trough_pitch| / max(1, n_phrase / 2))
   extrema_phrase = (apex + trough) / 2
   ```
   Đỉnh giá và đỉnh nốt lệch trong nửa câu thì điểm giảm dần.

2. **Độ rộng của câu (0.30)**
   ```text
   price_range = max(P) − min(P)
   pitch_range = max(pitch) − min(pitch)
   range_tau = Kendall tau-b(price_range, pitch_range)   # trên các câu
   ```
   Câu có biến động giá lớn phải có biên độ nốt lớn. Đây là phép so sánh **bất biến với đăng ký**, vì chỉ so độ rộng tương đối giữa các câu.

3. **Hướng lớn (0.20)**
   ```text
   trend = trung bình(
       1 nếu sign(P_end − P_start) == sign(pitch_end − pitch_start),
       0 nếu ngược
   )   # trên từng chương/section
   ```

Nếu bản có **ít hơn 4 câu** (1–3 câu), bỏ `range_tau` — Kendall tau trên 2–3 điểm không có ý nghĩa — và dùng `extrema` + `trend` với trọng số 0.7/0.3. Chỉ khi có **≥ 4 câu** mới dùng đủ ba thành phần 0.50/0.30/0.20.

### 4.7. Resolution — Độ phân giải

Mục tiêu: biến động giá có được “giải” thành thay đổi nốt không, và ngược lại.

Trên các cặp liên tiếp trong câu:

```text
price_moves = |ΔP| > εp
pitch_moves = |Δpitch| > εm

TP = price_moves & pitch_moves
FN = price_moves & !pitch_moves
FP = !price_moves & pitch_moves

recall    = TP / (TP + FN)
precision = TP / (TP + FP)
R = F1 = 2·precision·recall / (precision + recall)
```

- `εm = 1` semitone cho trace nốt; `εm = 2` cho centroid minimalist.
- Nếu không có `FP` (không có chuyển động thừa), dùng `R = recall`.
- Nếu không có `price_moves`, `R = null`.
- Đây là chỗ phạt ambient/minimalist khi texture chạy trong lúc giá đứng, và phạt các bản giữ nốt khi giá chạy.
- `bar_quantization_loss` trong `quantize.py` là một **chẩn đoán**, không đưa vào công thức để tránh đếm hai lần. Nếu `R` thấp mà loss cao, đúng như dự đoán; nếu lệch, trace có vấn đề.

### 4.8. Volume — Khối lượng

Volume không được mã hoá thành từng nốt; nó thành **band + mật độ + lực**. Vì vậy đo ở cấp cửa sổ:

Với mỗi cửa sổ `w`:

```text
V_w = window_volumes[w]               # average_liquidity(...) đã tính trong render.py
E_w = Σ(duration_beats × velocity × gain(marking)) / window_beats
```

`gain(marking) = SOUND[marking] / 90`: MuseScore phát **letter dynamic** đã in, không phát `NoteEvent.velocity`. Một bản có thể in p/mp/mf/f theo cửa sổ trong khi mọi velocity quanh 64; nếu chỉ đọc velocity thì volume thật bị chấm thành 0 dù tai nghe rõ to nhỏ. `gain` lấy từ chính `score.dynamics` (sự kiện đang có hiệu lực tại `bar/beat` của nốt), nên vẫn là "năng lượng thật" chứ không so band dự kiến với band đã in.

```text
V = max(0, Kendall tau-b(V_w, E_w))
```

- Chỉ dùng cửa sổ có `V_w > 0`.
- Cần ít nhất 4 cửa sổ và ít nhất 3 giá trị volume khác nhau; nếu không, `V = null`.
- Nếu `velocity` thiếu, dùng 64 (MusicXML default) và vẫn nhân `gain`.
- Không so band dự kiến với band đã in, vì writer có thể dịch band cho hợp âm sắc. So **volume thật** với **năng lượng thật** là đúng câu hỏi “volume có nghe ra không”.

Volume là phần dễ implement nhất vì chỉ cần đọc `NoteEvent` và cửa sổ đã có; không cần trace từng nốt.

### 4.9. Coverage — Độ phủ

Mục tiêu: đường giá có mặt ở những lúc giá chạy không. Đây là “hệ số pha loãng” đã bàn, đổi tên cho dễ hiểu.

**Coverage phải dùng lưới nguồn chung.** Nếu đo per-eighth cho Giao hưởng/Jazz/Guitar nhưng per-bar cho Ambient/Minimalist, `C` sẽ cao thấp một phần vì **độ mịn của lưới**, không vì cách mã hoá. Dùng musical bar làm đơn vị cũng không được: các variant có thể dùng form/`musical_bars` khác nhau (ví dụ 1D ambient và 1D ensemble). Vì vậy `C` đo trên **source bar**:

- Với mỗi source bar `s` (một phần tử của `bars`), tìm musical bar `m` sao cho `s ∈ groups[m]`. Nếu group có `k` source bar và `s` đứng thứ `pos` (0-based), khoảng musical của `s` là:
  ```text
  [m + pos/k, m + (pos + 1)/k]   # đơn vị: bar
  ```
- `sounding_s = 1` nếu có `PriceTracePoint` với `pitch != None` và khoảng nghe
  `[bar + beat/bar_beats, bar + (beat + duration_beats)/bar_beats]`
  giao với khoảng musical của `s`.
- Dùng `εp_s` = `εp_phrase` của câu chứa musical bar `m`:
  ```text
  w_s = max(|P_s − P_{s−1}|, εp_s)
  C = Σ(w_s × sounding_s) / Σ(w_s)
  ```
- Bỏ các source bar rơi vào section `warmup`, `cooldown`, `intro`, `outro`.
- Bỏ các source bar **trước nốt mang giá đầu tiên** và **sau nốt mang giá cuối cùng**. Ở `1D`, lead thường vào sau vài bar; đó là intro, không phải rest, nên không được phạt coverage. Rest **bên trong** khoảng có line vẫn bị phạt bình thường.
- Với `s = 0`, không có `P_{s−1}`; dùng `w_s = εp_s`.
- Rest lúc giá đứng gần như không bị phạt (`w_s = εp_s`).
- Rest lúc giá chạy bị phạt nặng (`w_s = |ΔP_s|`).
- Ambient ngân dài vẫn `sounding_s = 1`; nó bị phạt ở Shape/Motion, không phải Coverage. Nhờ vậy không phạt kép vì “ngân dài” vừa mất Motion vừa mất Coverage.
- Nếu `Σw_s = 0` (giá hoàn toàn đứng), `C = 1`; DFI sẽ `null` vì `n_moves = 0`.
- `coverage_detail` (per-eighth/per-bar theo variant) vẫn tính nhưng chỉ là **chẩn đoán**, không đưa vào DFI và không dùng để so chéo thể loại.

Cách chia đều này khớp với `resample(closes, eighths_per_bar)` trong `_compose`: các close trong một group được rải đều trên musical bar.

Lưới source bar là **cùng một tập `bars`** cho mọi variant/ensemble của cùng session/span. Đây là điều kiện để `C` so sánh chéo có nghĩa.

`C` là **hệ số nhân**, không phải một sub-score. Lý do: nếu đường giá vắng 40% thời gian có biến động, độ trung thực dữ liệu không thể vượt quá 60% dù những chỗ có mặt rất đúng.

### 4.10. Cơ hội, độ tin cậy, và band hiển thị

```text
opportunity = min(1, n_moves / 24)
```

Định nghĩa đơn vị:

- `n_moves`: số **bước trên lưới phân tích** (eighth/bar/anchor) có `|ΔP| > εp_phrase`, không phải số source bar.
- `n_sounding`: số **`PriceTracePoint` có `pitch != None`** (attack + hold + anchor), không phải số ô lưới.
- `n_sounding_source`: số source bar có ít nhất một trace point đang kêu; dùng cho chẩn đoán Coverage.

| Điều kiện | Confidence |
|---|---|
| `n_moves ≥ 24`, `n_sounding ≥ 48`, volume windows ≥ 8 | `high` |
| `n_moves ≥ 8`, `n_sounding ≥ 16` | `medium` |
| `4 ≤ n_moves < 8` | `low` |
| `n_moves < 4` | `null`, lý do `low_opportunity` |

Band hiển thị (tạm đặt, sẽ chỉnh sau calibration):

| Điểm | Nhãn |
|---:|---|
| 85–100 | Rất rõ |
| 70–84 | Rõ |
| 55–69 | Vừa |
| 40–54 | Mờ |
| 0–39 | Rất mờ |

UI hiện số nguyên; API trả float 1 chữ số thập phân. Với `low`, hiện `~78` hoặc một dấu chấm mờ; không giấu số.

---

## 5. Phân cấp: câu → chương → tác phẩm → thể loại/dàn nhạc

### 5.1. Trong một bản

| Cấp | Cách tính | Dùng để |
|---|---|---|
| **Câu** (`Phrase`) | S/M/T/R trên các điểm trong câu; C theo trọng số giá trong câu | Debug writer, xem câu nào làm mờ chart |
| **Chương** (`Movement`, span) | Tính DFI **trực tiếp** trên trace/source bar của cả chương | Hiển thị trong sheet khi nghe span |
| **Tác phẩm** (`1D` hoặc cả span) | Tính DFI **trực tiếp** trên trace/source bar gộp của tác phẩm | Con số `DFI` trên Stage |

Không lấy trung vị các điểm đã tính ở cấp dưới: DFI có phép nhân và `max(0, …)`, nên trung vị các điểm không bằng điểm tính trên dữ liệu gộp. Nếu cần một con số tổng hợp cho UI, tính lại từ trace gộp.

Khi cần trọng số giữa các chương (ví dụ hiển thị một dòng “trung bình chương”), dùng **số phách trong score** (`score.bar_beats × score.bars`), không dùng `durationSec` đã humanize/playback. Humanize có tempo curve; `durationSec` làm trọng số lệch khỏi cấu trúc nhạc.

Với `1D`, tác phẩm = một chương. Với `1W`–`1Y`, tác phẩm = nhiều chương; Stage hiện điểm tác phẩm, sheet hiện từng chương.

### 5.2. Chữ ký thể loại/dàn nhạc

Chữ ký **không phải** điểm của một bản. Nó là trung vị trên một corpus:

```text
signature(variant, ensemble, bucket) =
    median(DFI(piece) for piece in corpus)
```

- `bucket = "day"` cho `1D`, `"span"` cho `1W/1M/3M/1Y`. Form và khung khác nhau, không nên trộn.
- Corpus **paired**: cùng tập symbol-ngày (và cùng asOf cho span) được render cho mọi variant/ensemble. Nhờ vậy khác biệt phản ánh cách mã hoá, không phải chọn phiên may rủi.
- Chữ ký so sánh chéo variant chỉ đáng tin khi `C` dùng **source bar chung** (§4.9). Nếu vẫn dùng lưới riêng, chênh lệch `C` sẽ phản ánh mật độ grid, không phản ánh cách mã hoá.
- Loại các bản `null` hoặc `confidence = low`.
- Trả thêm `p25`, `p75`, `n`, `version`, `updatedAt`.
- Nếu tỷ lệ loại > 30%, đánh dấu signature `stale`; UI dùng giá trị cũ nhưng mờ hơn.
- Recompute khi `RECAP_REVISION` / `SPAN_REVISION` đổi, hoặc theo lịch tuần.

Corpus đề xuất ban đầu:

- 1D: 30–50 symbol thanh khoản × 20–60 phiên gần nhất.
- Span: 20 symbol × 4 range × 12 asOf.
- Cùng một bộ cho mọi variant/ensemble.
- Lưu artifact JSON (ví dụ `backend/app/sonify/fixtures/dfi_signatures.json`) kèm `dfi_version` và `sonify_revision`.

### 5.3. Kiểm tra tính nhất quán

Các kỳ vọng dùng làm test, không phải để ép kết quả:

1. `|DFI(wood) − DFI(classic)| ≤ 3` cho ≥ 90% bản giao hưởng; tương tự `brass`.
2. `|DFI(soul/organ) − DFI(classic)| ≤ 3` cho jazz; `mallet` gần minimalist; `breath/choir` gần ambient; `guitar` (thép) gần minimalist `classic`.
3. Guitar: sáu ensemble được phép lệch; Bach và Torroba thường cao hơn Villa/Barrios vì ít hoa mỹ che giá. Đây là **chẩn đoán**, không hard-code thứ hạng.
4. Trên corpus biến động: Giao hưởng/Jazz > Tối giản > Ambient. Ambient thấp hơn một phần vì Motion/Hình dạng phạt ngân dài — đó là chủ ý; Coverage chỉ phạt khi ambient nghỉ hẳn. Nếu Ambient > Tối giản, kiểm tra trace trước khi kết luận.
5. Phiên đi ngang: tất cả `null` hoặc `low`, không thể hiện 0 điểm.
6. Trước khi chốt trọng số, đo **ma trận tương quan** giữa `S`, `M`, `R` trên corpus. Nếu `R` gần như là hàm của `S` (vì trace bậc thang buộc đơn điệu), gộp `R` vào `S` hoặc trả bớt trọng số cho `R`, chuẩn hoá lại và ưu tiên `S`; Phase 7 quyết định.

---

## 6. UI trong replay

### 6.1. Nguyên tắc

- Luôn thấy khi đang nghe, nhưng không chiếm chỗ.
- Không dùng màu làm tín hiệu duy nhất; luôn có số/nhãn.
- Không biến thành bảng xếp hạng “thể loại hay nhất”.
- Không phân tích audio ở client; mọi số đến từ API.
- Chuyển thể loại/dàn nhạc vẫn dùng tile/shelf hiện có; sheet chỉ là nơi so sánh và chọn thêm.

### 6.2. Stage meta

Thêm một pill nhỏ vào dòng meta hiện tại (`ReplayRoom.tsx` dựng `stageMeta`, truyền qua `Stage.tsx`):

```text
VNM · 02/11 · C major · 90 BPM · 4:12 · DFI 78
```

- `DFI 78` bấm được, mở `DfiSheet`.
- Nếu `null`: `DFI —`.
- Nếu `low`: `DFI ~78`, opacity thấp hơn.
- `accessibilityLabel`: “Độ trung thực dữ liệu 78 trên 100, mức rõ”.

Không thêm một hàng mới; pill nằm trong dòng meta để không làm Stage cao lên.

### 6.3. Dưới genre shelf

Một spectrum mảnh, cao 3–4px, rộng ~120px:

```text
DFI  [██████████░░░░░░]  78
                  ↑
              chuẩn thể loại 74
```

- Phần đầy = điểm bản hiện tại.
- Vạch mảnh = trung vị thể loại/dàn nhạc đang chọn.
- Bấm vào spectrum mở sheet; không dùng làm control chọn thể loại để tránh hit target nhỏ.
- Chỉ hiện ở `mode="replay"`; live ẩn.

### 6.4. Ensemble shelf

- Ensemble đang chọn hiện thêm số nhỏ cạnh nhãn: `Bach · 81`.
- Các ensemble khác không hiện số ở shelf chính, tránh rối.
- Trong sheet, hiện đủ sáu dòng guitar kèm số và khoảng p25–p75.
- Với các thể loại không phải guitar, số của các ensemble thường gần nhau; hiện đủ để người nghe thấy “đổi âm sắc không đổi độ trung thực dữ liệu”.

### 6.5. `DfiSheet`

Một bottom sheet/popover mới, có thể tái dùng style của `OptionsPopover`.

**Nguồn dữ liệu cho cột “Cùng phiên/chương”:** cột này cần DFI của **cùng đơn vị đang nghe** render bằng variant/ensemble khác. `RecapResponse.dfi` chỉ có cho asset đang chọn, nên cần một endpoint compose-only:

```text
GET /v1/sonify/dfi/pieces
    ?symbol=VNM
    &bucket=day&date=2026-11-02
    &movement=0                 # bỏ qua với 1D; với span là chương đang nghe
    &variant=jazz&ensemble=classic
```

- Trả `DfiBreakdown | null` cho từng combo, kèm `cached`, `computedAt`.
- Với span, thay `date` bằng `range` + `asOf`; `movement` là chương đang nghe.
- **Bảng thể loại:** gọi 5 variant với `ensemble=classic` (dàn mặc định của từng thể loại) để cùng một thước đo. Nếu ensemble đang nghe khác `classic`, dòng đang chọn có badge “đang nghe” nhưng số trong bảng vẫn là `classic`; điểm của bản đang nghe nằm ở đầu sheet.
- **Bảng dàn nhạc:** gọi toàn bộ ensemble của variant đang chọn (3–6 combo).
- Với span, bảng so sánh **chương đang nghe**, không so cả tác phẩm; header ghi “Chương này”. Điểm tác phẩm vẫn ở đầu sheet.
- Server compose-only, **không export MuseScore**, cache sidecar theo `(symbol, bucket, date/asOf, movement, variant, ensemble, dfi_version, humanize)`; debounce/cancel nếu người dùng đổi qua lại.
- Dùng cùng `humanize`/`color` với bản đang nghe. Nếu khác humanize, chỉ so `S/M/T/R`; không so `V` vì velocity khác.
- Nếu endpoint chưa sẵn sàng hoặc lỗi: chỉ hiện dòng đang chọn + cột `Chuẩn`; các dòng khác `—`. Không chặn việc nghe.

```text
Độ trung thực dữ liệu                         78  (Rõ)
────────────────────────────────────────────
Hình dạng        ████████████████░░   0.84
Chuyển động      █████████████░░░░░   0.71
Cấu trúc         ██████████████░░░░   0.76
Độ phân giải     ████████████░░░░░░   0.63
Khối lượng       ██████████████░░░░   0.74
Độ phủ           █████████████████░   0.93
────────────────────────────────────────────
Cùng phiên 78   ·   Chuẩn thể loại 74 (70–79, n=412)
────────────────────────────────────────────
Thể loại            Cùng phiên   Chuẩn
Giao hưởng             78         74
Jazz                   81         77
Tối giản               66         64
Ambient                38         41
Guitar                 72         69
────────────────────────────────────────────
Dàn nhạc (Guitar)    Cùng phiên   Chuẩn
Bach                   84         79
Sor                    78         75
Barrios                74         71
Lobos                  70         68
Brouwer                72         69
Torroba                80         76
────────────────────────────────────────────
Điểm này đo mức phản ánh dữ liệu (giá và volume), không đo chất lượng âm nhạc.
```

- Mỗi dòng thể loại/dàn nhạc bấm được để đổi; highlight dòng đang chọn.
- Sub-score hiện thanh + số 0–1; không cần giải thích dài trong UI, chỉ tooltip/`accessibilityHint`.
- Nếu `volume = null`, dòng Khối lượng hiện `—` và có ghi chú “không có dữ liệu volume”.
- Nếu `null` toàn bộ: sheet hiện “Phiên ít biến động — không đủ cơ hội để chấm”.
- Với Ambient, thêm một dòng nhỏ: “Thưa là bản sắc; điểm thấp ở Chuyển động/Hình dạng là có chủ ý.” Không đổi số.

### 6.6. Copy tiếng Việt

| Thành phần | Copy |
|---|---|
| Pill | `DFI 78` |
| Sheet title | `Độ trung thực dữ liệu` |
| Band | `Rất rõ` / `Rõ` / `Vừa` / `Mờ` / `Rất mờ` |
| Shape | `Hình dạng` — “Đường giá và đường cao độ có cùng hướng không.” |
| Motion | `Chuyển động` — “Giá đi xa thì nốt có đi xa hơn không.” |
| Structure | `Cấu trúc` — “Đỉnh, đáy và hướng của cả câu có rơi đúng chỗ không.” |
| Resolution | `Độ phân giải` — “Biến động nhỏ có nghe ra, và texture có chạy khi giá đứng không.” |
| Volume | `Khối lượng` — “Volume lớn có nghe to và rõ hơn không.” |
| Coverage | `Độ phủ` — “Phần thời gian đường giá thực sự phát, tính theo mức biến động giá.” |
| Help | `DFI phản ánh mức nghe rõ của giá và volume, không phải độ hay của bản nhạc.` |
| Signature | `Chuẩn thể loại` / `Chuẩn dàn nhạc` |
| Disclaimer | `Điểm này đo mức phản ánh dữ liệu (giá và volume), không đo chất lượng âm nhạc.` |

Tránh các từ “điểm hay”, “xếp hạng”, “tốt nhất”.

---

## 7. API và dữ liệu

### 7.1. Schema

Thêm vào `backend/app/schemas.py`:

```python
class DfiBreakdown(BaseModel):
    score: float
    band: Literal["very-clear", "clear", "fair", "faint", "very-faint"]
    shape: float
    motion: float
    structure: float
    resolution: float
    volume: float | None = None
    coverage: float                 # source-bar, dùng trong công thức
    coverage_detail: float | None = None   # lưới riêng của variant, chỉ chẩn đoán
    opportunity: float
    confidence: Literal["low", "medium", "high"]
    version: str


class DfiSignature(BaseModel):
    variant: Literal["symphony", "jazz", "minimalist", "ambient", "guitar"]
    ensemble: str
    bucket: Literal["day", "span"]
    score: float
    p25: float
    p75: float
    n: int
    version: str
    updatedAt: str
    stale: bool = False


class DfiPiece(BaseModel):
    variant: Literal["symphony", "jazz", "minimalist", "ambient", "guitar"]
    ensemble: str
    movement: int | None = None
    dfi: DfiBreakdown | None = None
    cached: bool = False
    computedAt: str | None = None


class DfiPiecesResponse(BaseModel):
    symbol: str
    bucket: Literal["day", "span"]
    asOf: str
    pieces: list[DfiPiece]
```

`band` dùng `"fair"` cho khoảng 55–69; UI map sang nhãn `Vừa`. Không dùng `"mixed"` để tránh hai bộ từ vựng.

`DfiSignature.version` là version của **artifact corpus**, tách khỏi `DFI_VERSION` của metric; đổi công thức không tự đổi version chữ ký.

Gắn:

- `RecapResponse.dfi: DfiBreakdown | None = None`
- `SpanMovementResponse.dfi: DfiBreakdown | None = None`
- `SpanResponse.dfi: DfiBreakdown | None = None` (điểm tác phẩm)
- `SpanResponse.dfiMovements` không cần; đã có trong từng movement.

Endpoint chữ ký:

```text
GET /v1/sonify/dfi/signatures?variant=symphony&bucket=day
```

Trả tất cả ensemble của variant đó (hoặc tất cả variant nếu bỏ `variant`) để client fetch một lần. Cache `public, max-age=3600`.

Endpoint compose-only cho bảng so sánh trong sheet:

```text
GET /v1/sonify/dfi/pieces
    ?symbol=VNM
    &bucket=day&date=2026-11-02
    &movement=0
    &variant=jazz&ensemble=classic
```

- `bucket=day`: dùng `date`; `bucket=span`: dùng `range` + `asOf` + `movement`.
- `variant`/`ensemble` là filter; bỏ trống thì trả tất cả combo được yêu cầu (5 variant hoặc toàn bộ ensemble của một variant).
- Trả `DfiPiecesResponse`; không export audio.

### 7.2. Nơi tính và cache

- `render._compose` đã có `score`, `bars`, `groups`, `windows`, `window_volumes`, `bands`.
- Chỗ cắm `dfi.compute(...)` là `audio.py`: `RecapStore._render` (`audio.py:1394`) và `RecapStore._render_movement` (`audio.py:1233`), **sau** `humanize_score(score)`. `humanize_score` chỉ là alias của `humanize` trong `humanize.py`, re-export ở `audio.py:31`; humanize đổi velocity/tempo chứ không đổi `(bar, beat)`, nên trace vẫn khớp.
- Ghi `dfi` và `dfi_inputs` vào meta JSON cạnh audio. `dfi_inputs` là digest của `bars` (close + volume) mà score được dựng ra.
- Đọc lại trong `RecapAsset` / `SpanAsset`. Nếu `dfi_inputs` thiếu hoặc khác digest hiện tại (nến cuối đổi trong phiên live), coi như cache thiếu DFI và tính lại; **không hiển thị số của score cũ**. Endpoint plan cũng kiểm tra digest và trả `dfi = null` nếu lệch, để client biết còn phải chờ.
- Với cache cũ chưa có `dfi`: **không bump `RECAP_REVISION`** (sẽ render lại toàn bộ audio rất đắt). Thay vào đó:
  1. Khi đọc cache thiếu `dfi` (hoặc digest lệch), compose lại score (không export MuseScore), tính DFI, ghi `dfi` + `dfi_inputs` vào meta.
  2. Nếu compose lại lỗi, log warning, trả `null`; audio cache vẫn phát bình thường. UI hiện `DFI —`.
- Sidecar key đã chứa `dfi_version`, `RECAP_REVISION`/`SPAN_REVISION`, `variant`, `ensemble`, `humanize`, `color`, `date`/`movement`, và digest của `bars`. Các input còn lại (`groups`, form/spec) là hàm của `bars` + form nên không cần hash riêng.
- Sidecar có `dfi_version`; đổi version thì tính lại sidecar, không đụng audio.
- Sidecar được dọn theo TTL 14 ngày, kiểm tra tối đa mỗi giờ, để endpoint compose-only không làm đầy đĩa.
- **Ops sau khi deploy DFI:** xoá một lần `var/audio/pafi/` (sidecar của tên cũ). Code mới chỉ đọc/ghi `var/audio/dfi/` và không tự xoá thư mục cũ.

### 7.3. Hiệu năng

- DFI chỉ đọc `NoteEvent` + trace; mục tiêu < 50ms/bản.
- Không gọi MuseScore, không đọc WAV.
- Signature là artifact tĩnh; API chỉ đọc JSON.
- Endpoint `dfi/pieces` là compose-only (không export). Mục tiêu < 300ms/combo khi ấm cache, < 2s cho 5–11 combo khi nguội; phải có cache sidecar, debounce và cancel. Nếu vượt ngân sách, sheet fallback về “dòng đang chọn + Chuẩn”.

---

## 8. Kế hoạch implement

### Phase 0 — Trace, không đổi âm thanh

- Thêm `PriceTracePoint` và `Score.price_trace` (mặc định rỗng).
- Ghi trace cho Giao hưởng và Jazz từ `pitches` / `sax_pitches`.
- Test: mọi trace point `role in {"attack","anchor","register"}` phải khớp một `NoteEvent` tại cùng `(bar, beat)` (trừ `hold`/`rest` có ghi chú); `duration_beats` phải phủ đúng khoảng đang kêu. Thêm utility `eighth ↔ (bar, beat)` cho các test lưới.
- Test: các nốt price-bearing phải có trace; nốt trang trí/đệm không được có trace.
- Chưa đổi UI/API.

### Phase 1 — Minimalist, Ambient

- Minimalist: ghi `role="register"`, `pitch = centroid` của cửa sổ arpeggio mỗi bar.
- Ambient: ghi `role="anchor"` tại anchor; ghi `hold` khi glass ngân; ghi `rest` khi breath không mang giá.
- Test synthetic: giá lên đều → centroid/anchor lên; giá đứng → giữ.

### Phase 2 — Sáu guitar writer

- Bach: chỉ móc kép chẵn.
- Torroba: chỉ nốt phách mạnh.
- Villa/Barrios: trace đổi voice theo pattern, gồm `thumb_cantabile`.
- Sor/Brouwer: trace theo lead; bỏ nốt quãng 3/6 và scale overlay.
- Test từng ensemble trên fixture có sẵn; so với “nốt cao nhất” để chứng minh trace đúng hơn.

### Phase 3 — Metric + test

- Viết `backend/app/sonify/dfi.py`: `compute`, `shape`, `motion`, `structure`, `resolution`, `volume`, `coverage`, `band`.
- Test synthetic:
  - Giá tăng đơn điệu, nốt tăng đơn điệu → `S ≈ 1`, `R ≈ 1`.
  - Giá tăng, nốt giảm → `S = 0`.
  - Giá đứng, nốt chạy → `R` thấp.
  - Giá chạy, nốt giữ (`hold` có `duration_beats` phủ bar nguồn) → `C ≈ 1`, `M`/`R` thấp; không phạt kép Coverage.
  - Rest lúc giá chạy → `C` thấp.
  - Cùng một trace, đổi `groups` để musical bar phủ nhiều source bar hơn → `C` vẫn tính trên source bar, không đổi theo mật độ grid.
  - Volume tăng đơn điệu, năng lượng tăng → `V ≈ 1`; volume ngẫu nhiên → `V ≈ 0`.
  - `n_moves < 4` → `None`.

### Phase 4 — API + cache

- Thêm schema, gắn vào recap/span.
- Sidecar cho cache cũ, có `inputs_hash` và hành vi trả `null` khi lệch.
- Endpoint signature và endpoint compose-only `dfi/pieces` cho bảng so sánh trong sheet.
- Test API: recap/span trả `dfi`; cache cũ trả `null` hoặc sidecar; `dfi/pieces` trả đủ combo, cache ấm, cancel khi đổi variant; không làm chậm đáng kể.

### Phase 5 — Signature corpus

- CLI/job tính corpus paired.
- Sinh artifact JSON.
- Kiểm tra các kỳ vọng ở §5.3.
- Gắn `version`, `updatedAt`, `stale`.

### Phase 6 — UI

- `Stage` pill.
- Spectrum dưới genre shelf.
- Ensemble numeral.
- `DfiSheet` + chọn thể loại/dàn nhạc.
- Accessibility, loading, `null`, `low`.
- Test format số, band, copy.

### Phase 7 — Calibration

- Chạy corpus thật; xem phân bố.
- Đo ma trận tương quan `S/M/R/T`; nếu `R` gần như hàm của `S`, gộp `R` vào `S` hoặc trả bớt trọng số cho `R`. Ghi quyết định vào version.
- Kiểm tra `V` có bão hoà không (median gần 1, ít phân biệt); nếu có, giữ 0.10 hoặc giảm nữa, dồn sang `S`/`T`.
- Chỉnh `εp_phrase` (nhất là sàn 5 bps), trọng số, ngưỡng band nếu cần.
- So sánh với một panel nghe nhỏ (5–10 người, 20 clip): Spearman giữa DFI và xếp hạng cảm nhận. Mục tiêu > 0.6; nếu thấp, xem lại trace/trọng số.
- Chốt `dfi_version` mới khi công thức/trọng số thay đổi; hiện tại là `"3"`.

Ước lượng: 7–10 ngày làm việc (gồm endpoint compose-only cho bảng so sánh), chưa gồm calibration nghe.

---

## 9. Rủi ro và cách chặn

| Rủi ro | Hậu quả | Cách chặn |
|---|---|---|
| Trace bắt nhầm nốt hoa mỹ | Điểm thấp/sai cho Bach, Torroba, Villa | Trace do writer/`_attach_dfi_inputs` xác định; test “nốt cao nhất” phải thua trace |
| Writer đổi mà quên trace | DFI lệch âm thầm | Test consistency: trace ↔ `NoteEvent`; golden test |
| Jazz dịch octave ở biên câu | Shape/Motion sai | Chỉ so trong câu; không gộp level toàn bản |
| Ambient ngân dài | Điểm thấp | Đúng với “độ trung thực dữ liệu”; Motion fallback anchor-to-anchor khi quá ít cặp; UI ghi “thưa có chủ ý”, không gọi là lỗi |
| Minimalist nhiều nốt trang trí | Precision thấp | Trace chỉ ghi centroid, không ghi từng nốt arpeggio |
| Volume band quá thô | Volume score bão hoà | So hạng, không so giá trị tuyệt đối; cần ≥ 4 cửa sổ; hạ trọng số còn 0.10 |
| Coverage khác lưới giữa variant | So chéo thể loại sai | `C` dùng source bar chung; `coverage_detail` chỉ chẩn đoán |
| `S/M/R` chồng lấn | Trọng số nhân đôi cùng một tín hiệu | Đo correlation matrix ở Phase 7; gộp `R` vào `S` nếu cần |
| Sidecar dùng input khác audio cache | DFI không khớp bản đang nghe | `inputs_hash`; lệch thì trả `null`, không ghép |
| Phiên ít biến động | Điểm 0/100 giả | Trả `null` khi `n_moves < 4`; hiện `DFI —` |
| Dùng DFI để chọn “thể loại hay” | Sai mục tiêu | Copy và UI tách “độ rõ” khỏi “chất lượng” |
| Corpus lệch regime | Signature sai | Paired corpus cùng symbol-ngày; median; p25/p75 |
| Metric bị game bởi writer | Nhạc mất tự nhiên | Giữ test nhạc tính hiện có; calibration nghe |

### 9.1. Sai lệch đã biết so với thiết kế ban đầu

- **Trace không phải lúc nào cũng ghi tại chỗ viết nốt.** Guitar ghi qua `_TRACE_LINE` / `_TRACE_PRICE_LINE`; các variant còn lại dựng trace trong `_attach_dfi_inputs` từ `score.lead` (hoặc lead+support+low). Hệ quả: nốt đệm/hoa mỹ trùng cao độ với đường giá có thể bị nhận nhầm, và `n_sounding` (dùng cho confidence) chênh giữa các ensemble. Với Torroba, trace dùng **ý đồ** trước khi hạ quãng/đổi bè, nên đo “writer định đặt giá ở đâu” hơn là “tai nghe thấy gì”. Nếu đường giá chuyển sang bè mà helper không đọc (ví dụ coda giao hưởng), coverage sẽ **conservative** — thấp hơn thực tế; sửa gốc vẫn là ghi trace tại writer.
- **`role` mới dùng `attack/anchor/register`.** `hold` và `rest` có trong model nhưng writer chưa phát; coverage suy ra từ khoảng nghe của trace point thay vì role.
- **`low-evidence` chưa surface.** `_motion` tính cờ fallback nhưng `compute()` bỏ qua; UI chỉ thấy `confidence` tổng.
- **Band chưa calibration.** Trên phiên êm tổng hợp, điểm cao nhất đã lên 74–78 sau các fix; corpus thật chưa chạy. Band `Rõ` (70) và `Rất rõ` (85) có thể đạt sau Phase 7; giữ nguyên ngưỡng thay vì hạ cho đẹp số.
- **Thứ hạng trên phiên biến động mạnh** có thể là minimalist > symphony > jazz > ambient, ngược kỳ vọng §5.3 #4. Nguyên nhân là `quantize_strong_beats` bẻ đường giá về hợp âm ở phách mạnh (S/T thấp trong khi M cao), không phải trace sai. Đây là input cho Phase 7.

---

## 10. Quyết định đã chốt và điểm cần calibration

Đã chốt sau feedback:

1. **Tên hiển thị:** pill `DFI`, sheet `Độ trung thực dữ liệu`. Pill có `accessibilityLabel` đầy đủ.
2. **Coverage là hệ số nhân `C^1`:** giữ, nhưng `C` đo trên **source bar chung**, không đo trên lưới riêng của từng variant (§4.9). Không dùng `C^0.75` để “làm mềm” trước khi sửa cấu trúc.
3. **Trọng số:** `S 0.33`, `M 0.21`, `T 0.19`, `R 0.17`, `V 0.10`. Volume giảm còn 0.10; 0.02 dồn vào Cấu trúc. Phase 7 xác nhận.
4. **Signature tách bucket `day`/`span`:** giữ.
5. **Shelf chính chỉ hiện số của ensemble đang chọn:** giữ; tất cả nằm trong sheet.
6. **Ambient:** thêm dòng “thưa là bản sắc” trong sheet; Motion vẫn phạt ngân dài qua giá chạy, nhưng có fallback anchor-to-anchor khi quá ít cặp.
7. **Coverage bỏ phần lead chưa vào:** source bar trước trace point đầu tiên và sau trace point cuối cùng là frame, không phải rest (§4.9). Rest bên trong khoảng có line vẫn bị phạt.

Cần calibration / quyết định ở Phase 7:

8. **`R` có bị `S` nuốt không:** đo correlation matrix; nếu `R` gần như hàm của `S`, gộp hoặc giảm trọng số `R`.
9. **`V` có bão hoà không:** nếu median gần 1 và ít phân biệt, giữ 0.10 hoặc giảm nữa.
10. **Sàn `εp`:** 5 bps (`0.0005 × median(close)`) là khởi điểm; chỉnh theo volatility.
11. **“Cùng phiên/chương” trong sheet:** dùng endpoint compose-only `dfi/pieces` (§6.5, §7.1); nếu lỗi/chưa sẵn sàng, fallback chỉ hiện dòng đang chọn + `Chuẩn`.
12. **Cache cũ:** meta ghi `dfi_inputs` (digest của bars); thiếu hoặc lệch thì tính lại, không ghép DFI của score khác vào audio đang cache.

---

## 11. Tóm tắt một dòng

DFI đo **mức phản ánh dữ liệu nguồn** (hiện tại: giá + volume) bằng năm thành phần — hình dạng 0.33, chuyển động 0.21, cấu trúc 0.19, độ phân giải 0.17, khối lượng 0.10 — nhân với **độ phủ theo source bar**, chuẩn hoá theo cơ hội, lấy từ **trace do writer xác định** chứ không suy từ nốt cao nhất; hiển thị kín đáo trong replay và so sánh bằng **trung vị corpus** cho từng thể loại/dàn nhạc.
