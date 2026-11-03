# Parameter profile và bàn tinh chỉnh — Kế hoạch V1

> **Trạng thái**: đã đối chiếu code, chưa code.
>
> **Liên kết**: [`sonify-humanize-preset-plan.md`](./sonify-humanize-preset-plan.md), [`musicalize-ui-redesign.md`](./musicalize-ui-redesign.md).
>
> **Mục tiêu**: tách các parameter tầng A ra khỏi code, lưu hành vi hiện tại thành `Default`, cho phép tạo profile có tên, và mở một bàn tinh chỉnh ngay trong phòng nghe.

---

## 0. Sửa sau các vòng đối chiếu code

Sáu lỗi chặn và ba lỗi kỹ thuật đã được xử lý trong bản này:

| # | Vấn đề | Cách sửa trong doc |
|---|---|---|
| 1 | `tempo` không phải phép nhân thuần trên guitar: `BARRIOS_TREMOLO_MIN_BPM = 90` quyết định **có viết tremolo hay không**, và writer đọc `ctx.bpm`. | BPM hiệu lực được đặt **trước khi writer chạy**; dưới 90 thì tremolo tự rơi. Không clamp. §3.2 |
| 2 | `humanize` nhân nhầm `CAP` hai vai trò (trần offset và ngưỡng freeze), cộng banker's rounding làm 5 bước slider không đổi gì. | Tách `FREEZE_GAP = 2` khỏi `offset_cap = 2 × humanize`; làm tròn xác suất để nửa trên của knob vẫn đổi. §3.4 |
| 3 | `prune()` xoá mọi file không khớp `_STORED_NAME`, chạy mỗi lần `get()`. | Blocker Phase 0: sửa regex + test “render profile mới xong không bị xoá”. §6.2 |
| 4 | DFI recompose ngoài audio dùng key không có `params_hash`; `dfi_inputs` được so ở cả `sessions.py` và `spans.py`. | Thread hash vào `_recap_key`, `_movement_key`, `dfi_inputs` (cả recap lẫn span) và `/dfi/pieces`. §6.4 |
| 5 | Legacy `h=0` bỏ hẳn `humanize()` (không tempo clock, không `_clamp_guitar`), nên tái dùng `_nh` sẽ phát sai tiếng. | `h=0` map thành `{humanize: 0, breath: 0}`; skip `humanize()` khi cả hai bằng 0; guard `_clamp_guitar`; `_nh` chỉ dùng cho đúng tổ hợp legacy. §6.1 |
| 6 | `Score.bpm`, `_Ctx.bpm`, `render_guitar_score`, `_metronome` đều là `int`, trong khi doc ghi `86.4`. | BPM hiệu lực là **int**; không nới kiểu. Bỏ mọi ví dụ lẻ. §3.2 |
| 7 | Guard `if offsets:` không chặn `_clamp_guitar`, vì `offsets` có key với giá trị 0. | Dùng `any(offsets.values())` hoặc bỏ `setdefault` khi `humanize = 0`. §6.1 |
| 8 | `round()` cho BPM dính banker's ở `.5`, làm BPM không đơn điệu. | `int(x + 0.5)` half-up. §3.2 |
| 9 | “Bit hash thứ hai” chưa ràng buộc nguồn, dễ dùng `hash()` bị randomize. | Lấy từ FNV `value`, ví dụ `(value >> 16) & 1`; test hai `PYTHONHASHSEED`. §3.4 |

Các điểm “nên sửa” còn lại đã vào §3.1–§3.7, §5, §6.3, §6.5, §8, §10, §12.

---

## 1. Quyết định đã chốt

| # | Quyết định |
|---|---|
| 1 | V1 chỉ làm **tầng A** — parameter an toàn, hiệu quả cao. Tầng B (form, harmony, register) và tầng C (thuật toán guitar, trọng số Viterbi) để sau. |
| 2 | Hành vi hiện tại được lưu nguyên vẹn thành **`Default` profile**; score/MusicXML của Default phải bất biến. Audio Default đổi **một lần, có chủ ý** ở revision 80 khi `noise` chuyển sang % tuyệt đối và có bed trên cả 5 variant; đây là thay đổi được ghi nhận, không phải drift âm thầm. |
| 3 | Profile có **tên**, tạo được, **đổi tên** được, nhân bản, xoá, reset. |
| 4 | UI mở thành **drawer từ cạnh phải** trên màn rộng và **sheet từ dưới lên** trên điện thoại. Không mở inline để không đẩy chart và không bắt người dùng scroll. Chi tiết ở §8. |
| 5 | **Chưa cần auth**. V1 chưa có profile server theo user. |
| 6 | Chưa làm AI tạo profile, chưa làm tầng B/C. Chỉ chỉnh tầng A trước. |
| 7 | `tempo` thấp làm rơi tremolo guitar là **hành vi được chấp nhận**, không clamp BPM. Writer dùng BPM hiệu lực, nên chọn pattern và score luôn nhất quán. BPM hiệu lực là **số nguyên**; không cần phần lẻ. |
| 8 | `humanize` là knob **liên tục 0–2.0, step 0.05**. Trần offset tách khỏi ngưỡng freeze. Trên `1.5` nhóm base `±2` đã bão hoà ở `±3`, chỉ nhóm `±1` còn tăng; `1.0` là mức khuyến nghị, cảnh báo từ `> 1.1`; `1.5` là trần kỹ thuật của nhóm chính. |
| 9 | Cache non-default dùng **LRU theo `params_hash`**, không giữ mọi hash 30 ngày. Default được pin; legacy `_nh/_nc` chỉ pin khi params đúng tổ hợp legacy. |
| 10 | Legacy `h=0` giữ cache cũ bằng cách map thành `{humanize: 0, breath: 0}`, skip `humanize()` khi cả hai bằng 0, và guard `_clamp_guitar`. `p{humanize: 0}` (breath vẫn 1) là bản khác, dùng `_p<hash>`. |
| 11 | State profile nằm ở **`MusicalizeApp`**, nơi chỉ render một room tại một thời điểm; `RoomFrame` chỉ render panel. Không nhân đôi hook ở `LiveRoom` và `ReplayRoom`. |

### Đề xuất kỹ thuật đi kèm

- `Default` là profile **bất biến**, nằm ở server và được bundle trong app để so khớp.
- Profile người dùng lưu **local** (AsyncStorage). Chia sẻ bằng URL chứa parameter đã chuẩn hoá.
- Built-in preset đơn giản nằm ở server, không cần auth.
- Cache audio dùng **`params_hash`**; Default không đổi tên file để không thêm biến thể cache. Revision vẫn tăng khi âm thanh Default đổi, nên file audio cũ có thể bị `prune()`; `_nh/_nc` giữ đúng âm thanh legacy, không hứa tái dùng file cũ.
- DFI của bản non-default vẫn được tính và lưu, nhưng **cột so sánh corpus chỉ hiện với Default** trong V1.

---

## 2. Vấn đề

Pipeline hiện tại:

```text
render(spec, ctx.bpm)  →  humanize()  →  MusicXML  →  MuseScore  →  FFmpeg preset  →  .m4a
```

Parameter nằm rải rác trong code:

| Nhóm | Ví dụ | File |
|---|---|---|
| Form / tempo | `MUSICAL_BARS = 30`, `BPM = 90`, phrase 8 bar, meter 4/4–12/8 | `backend/app/sonify/form.py` |
| Tempo theo dòng | `JAZZ_BPM = 82`, `MINIMALIST_BPM = 118`, `AMBIENT_BPM = 60`, `GUITAR_BPM` 88–120 | `jazz.py`, `minimalist.py`, `ambient.py`, `guitar.py` |
| Ngưỡng guitar | `BARRIOS_TREMOLO_MIN_BPM = 90` chọn tremolo / sixteenths theo `ctx.bpm` | `guitar*.py`, `guitar_patterns.py` |
| Dynamics | bảng velocity `p/mp/mf/f`, trần bass `mp`, velocity piano | `dynamics.py` và 53 điểm đọc rải rác |
| Humanize | `CAP = 2` vừa là trần offset vừa là ngưỡng freeze; `_TEMPO_DELTA`, Torroba 3.5%/5%, trần 10%, lilt 4% | `humanize.py` |
| Mix / màu | chuỗi FFmpeg từng variant, noise `%` tuyệt đối, gate `0.01` | `preset.py` |
| Render | MuseScore binary, soundfont, số slot export, AAC filter | `audio.py` |

UI hiện tại chỉ có `variant`, `ensemble`, `humanize` bật/tắt, `color` bật/tắt trong `src/musicalize/OptionsPopover.tsx`. URL chỉ mang `h=0/1` và `c=0/1` (`src/musicalize/link.ts`).

### Hệ quả

- Muốn thử một ý tưởng phải sửa Python, tăng `RECAP_REVISION` / `SPAN_REVISION`, deploy, rồi chờ render lại.
- Không có A/B, không có profile, không có URL chia sẻ cấu hình.
- Cache bị xoá hàng loạt mỗi lần đổi một con số.
- Người dùng và AI không có bề mặt nào để tạo biến thể.

---

## 3. Phạm vi V1 — tầng A

### 3.1 Bảy knob

Tất cả đều là số thực; phần lớn là **hệ số** mặc định `1.0`, riêng `noise` là biên độ tuyệt đối, để một profile dùng được cho mọi variant.

| Key | Nhãn UI | Khoảng | Bước | Default | Ý nghĩa |
|---|---|---:|---:|---:|---|
| `tempo` | Nhịp | `0.75 – 1.25` | `0.01` | `1.00` | Nhân BPM gốc của variant. 1.0 = đúng hiện tại. |
| `humanize` | Người | `0.00 – 2.00` | `0.05` | `1.00` | Độ lệch velocity. 0 = máy hoàn toàn; 1 = hiện tại; 1.5 = trần offset ±3, trên 1.5 chỉ còn nhánh ±1 tăng. |
| `breath` | Hơi thở | `0.00 – 2.00` | `0.05` | `1.00` | Nhân độ cong tempo trong câu. 0 = phẳng; 1 = hiện tại. |
| `dynamics` | Tương phản | `0.50 – 1.50` | `0.05` | `1.00` | Co giãn velocity quanh mốc 64. 1 = bảng p–f hiện tại. |
| `color` | Màu | `0.00 – 2.00` | `0.01` | `1.00` | Lượng wet của preset. 0 = khô; 1 = chuỗi hiện tại; 2 = đậm gấp đôi. |
| `noise` | Nhiễu | `0.00 – 0.50` | `0.05` | `0.10` | Nhiễu nền tuyệt đối, % full-scale. 0 = không nhiễu; 0.5 = −46 dBFS. |
| `density` | Mật độ | `0.00 – 2.00` | `0.05` | `1.00` | Nhân độ dài/số lượng fill và bell. 0 = không fill/bell; 1 = hiện tại; 2 = gấp đôi. |

### 3.2 `tempo` — BPM hiệu lực, không phải phép nhân hậu kỳ

`tempo` **không** được áp sau khi score đã viết. Nó phải có hiệu lực trước khi writer guitar đọc `ctx.bpm` và trước `humanize()`:

1. Chọn `spec` của variant như hiện tại.
2. `effective_bpm = int(spec.bpm * tempo + 0.5)` — **int**, làm tròn **half-up**.
3. Truyền `effective_bpm` vào `render()` và vào `ctx.bpm`; không mutate `DAILY_SPEC` hay spec global.
4. `score.bpm = effective_bpm` trước `humanize()` và trước `piece_seconds()`.

Không dùng `round()` trần vì banker's rounding làm BPM không đơn điệu ở đúng mốc `.5`: `90 × 0.85 = 76.5 → 76`, còn `90 × 0.95 = 85.5 → 86`. Half-up cho `77` và `86`, nhất quán với cách xử lý ở `humanize`.

Không nới `Score.bpm`, `_Ctx.bpm`, `render_guitar_score` hay `_metronome` sang `float`; tất cả đang là `int` và giữ nguyên. Hệ quả: hai bước `tempo` liền nhau có thể cho cùng một BPM ở dòng nhạc chậm; UI hiện BPM suy ra nên người dùng thấy ngay. Không ép BPM chẵn vì sẽ làm tempo thô; mọi BPM gốc vốn đã chẵn nên Default không đổi.

Hệ quả đã chốt: các ngưỡng guitar dùng **BPM hiệu lực**, nên hạ tempo có thể làm rơi tremolo/sixteenths:

| Ensemble | BPM gốc | `tempo` làm rơi ngưỡng 90 |
|---|---:|---|
| `torroba` | 96 | `≤ 0.93` (90/96) |
| `villa` | 100 | `< 0.90` (90/100) |
| `bach` | 96 | `≤ 0.93` |
| `brouwer` | 108 | `≤ 0.82` (`0.83 × 108 = 89.64` làm tròn lên 90, vẫn còn tremolo) |
| `classic` (module `guitar_sor.py`) | 88 | đã dưới 90 ở Default |

Đây là **hành vi đúng**, không phải lỗi: nếu bản chậm đến mức không còn tremolo thì viết tremolo sẽ sai nhạc. UI hiện BPM suy ra và, với guitar, ghi chú “dưới ngưỡng tremolo” khi BPM hiệu lực < 90. Test bắt buộc: `torroba` ở `tempo = 0.9` cho 86 BPM, không có tremolo, và `<per-minute>` ghi `"86"`.

### 3.3 `breath` — nhân độ cong, có bão hoà

`_tempo_clock()` nhân `_TEMPO_DELTA`, `_TORROBA_OPEN_DELTA`, `_TORROBA_CLOSE_DELTA`, `_LILT_DELTA` với `breath`. Trần an toàn `_TEMPO_CAP = 0.10` giữ nguyên; khi tổng vượt trần, cả câu được scale về đúng 10% (`humanize.py:526`).

Vì vậy `breath` **bão hoà**: từ điểm peak chạm trần, tăng tiếp không làm cong thêm. Điều này chấp nhận được nhưng phải test và phải nói trên UI:

- `breath = 0` trả `tempos = ()`.
- `breath = 1` khớp tuyệt đối hiện tại.
- `breath = 1.5` phải lệch nhiều hơn `1.0` trên variant còn dư trần (symphony, jazz, minimalist, ambient).
- Torroba gần trần sẵn; test riêng để ghi nhận bão hoà thay vì giả định tuyến tính.
- Cảnh báo mềm khi `breath > 1.2`.

### 3.4 `humanize` — tách trần offset khỏi ngưỡng freeze

Hiện tại `CAP = 2` làm hai việc:

- trần offset trong `_clamp_offset` (`humanize.py:152`);
- ngưỡng “freeze plateau” trong `_movable` (`humanize.py:145-147`).

Nhân đôi `CAP` sẽ đổi cả cấu trúc freeze, không chỉ biên độ. Đồng thời `round(2 * humanize)` là banker's rounding: `1.25 → 2`, phải `1.3` mới lên `3`, nên 5 bước slider không đổi gì.

Cách làm chốt:

- `FREEZE_GAP = 2` cố định. `_movable` luôn so với 2, không phụ thuộc knob.
- `chosen_offset` vẫn dùng FNV trên `(variant, ensemble, field, bar, tick)` để ổn định giữa process:
  - `base = _CHOICES[value % 5]` như hiện tại;
  - `target = base * humanize` (float);
  - `offset = sign(target) * stochastic_round(|target|)`, phần lẻ lấy từ **chính `value` FNV**, ví dụ `(value >> 16) & 1`.
- **Không dùng `hash()` của Python** để chọn bit làm tròn: `hash()` được randomize mỗi process (`humanize.py:60` đã ghi chú đúng điều này). Nếu dùng, cùng params sẽ ra offset khác giữa các lần chạy → audio khác, cache và test parity flake. Test phải chạy hai process với `PYTHONHASHSEED` khác nhau và so offset.
- **Không dùng `int()` cắt xuống.** Nếu cắt, `humanize = 1.05` cho `base ±2 → 2.1 → 2`, nên nửa trên của knob gần như đứng yên. Làm tròn xác suất cho `2.1 → 2` với 90% và `3` với 10%, nên 0.05 bước vẫn đổi biên độ cảm nhận được; `2.5 → 2/3` theo 50/50.
- Trần thực tế là `ceil(2 × humanize)`; không cần clamp riêng vì `|target| ≤ 2 × humanize`. Nếu vẫn giữ `_clamp_offset`, clamp **sau** khi làm tròn, không clamp float rồi cắt int.
- Ở `humanize = 1`, `target` là số nguyên → offset **trùng tuyệt đối** hiện tại, đảm bảo Default parity.
- `humanize = 0` → offset 0 toàn bộ.
- `humanize = 1.5` → trần ±3. Trên `1.5` nhóm base `±2` bão hoà, `2.0` chỉ còn tăng nhóm `±1`. Đây là trần kỹ thuật, không phải mức khuyến nghị: `sonify-humanize-preset-plan.md` đã loại ±3 vì làm phẳng contour. **`1.25` cũng đã có thể ra ±3**: `base ±2 → 2.5`, 50% ra 3. Vì vậy `1.0` là mức khuyến nghị, cảnh báo mềm bắt đầu từ `> 1.1`, và AC phải kiểm tra contour ở cả `1.25` lẫn `1.5`.

Range dừng ở `1.5`, step `0.05`, cảnh báo mềm khi `> 1.1`.

### 3.5 `dynamics` — suy ra `<sound>` từ velocity

`dynamics.py` hiện có `SOUND` và `PIANO_VELOCITY`; có **53 điểm đọc** ngoài module. Hai điều bắt buộc:

1. `sound_for(marking)` phải **suy ra từ `velocity_for(marking)`**: `sound% = round(velocity / 90 * 100)` (forte = velocity 90, `dynamics.py:7-9`). Không scale percent quanh 71 và velocity quanh 64 riêng, nếu không `<sound dynamics>` và `<note dynamics>` lệch nhau.
2. Mọi nơi đọc `SOUND[...]`, `PIANO_VELOCITY[...]`, `FILL_VELOCITY` phải đi qua hàm. Thêm test cấm import trực tiếp các dict này ngoài `dynamics.py`.

Tương tác với humanize: dynamics đổi velocity **trước** humanize, nên nó đổi luôn cổng freeze. Phải có test ghép `dynamics 1.5 × humanize 1.5`, không chỉ test từng knob.

### 3.6 `color` — `ColorSpec` có kiểu, không nhân chuỗi

Chuỗi hiện tại trộn bốn loại tham số khác đơn vị (`preset.py:25-32`): `highshelf g=-2`, `equalizer g=1.5`, `aecho delay|decay`, `asoftclip threshold=0.9`. Không thể định nghĩa “amount” tuyến tính trên cả bốn.

Chốt: thay chuỗi hardcode bằng `ColorSpec` có kiểu:

```python
@dataclass(frozen=True)
class ColorSpec:
    highshelf_db: float
    eq_db: float
    echo: tuple[tuple[int, float], ...]   # (delay_ms, decay)
    softclip_threshold: float
```

`amount` (0–2) biến đổi:

- gain dB nhân `amount`;
- decay nhân `amount`;
- `softclip_threshold` lerp về `1.0` (bypass) khi `amount → 0`;
- delay giữ nguyên, chỉ bỏ tap khi decay = 0;
- `amount = 0` bỏ hẳn filter màu, dùng WAV khô.

`amount` có thể vượt `1` (lên `2`) để đậm hơn preset gốc: gain, decay và ngưỡng soft-clip vẫn nằm trong dải hợp lệ.

Chuỗi FFmpeg được **sinh** từ spec theo thứ tự cố định. Ở `amount = 1`, chuỗi phải **giống từng byte** chuỗi hiện tại; test khoá chuỗi Default cho cả 5 variant. Mọi giá trị khác là kết quả của spec, không phải “mò hệ số”.

### 3.7 `density` và `noise`

- `density` nhân `FILL_SPAN`, `FILL_MIN`, `BELL_MAX_EIGHTHS` trong `phrasing.py`; `0` bỏ fill/bell, `1` giữ nguyên, `>1` kéo dài trong giới hạn an toàn. Không chỉnh số nốt giai điệu, không chỉnh guitar pattern.
- `noise` là biên độ tuyệt đối tính bằng % full-scale (`0–0.5%`), không phải hệ số nhân. Guitar giữ gate `0.01`; mọi variant đều nhận nền nhiễu, kể cả khi `color = 0`. Nhiễu trộn sau chuỗi màu, trước peak limit.

### 3.8 Thứ tự triển khai trong tầng A

- **A1 — performance + mix**: `tempo`, `humanize`, `breath`, `color`, `noise`.
- **A2 — texture**: `dynamics`, `density`.

A1 chạm ít module hơn và cho cảm nhận rõ nhất. A2 chạm `dynamics.py` và `phrasing.py`, làm sau khi A1 ổn định.

### 3.9 Ngoài phạm vi V1

- Form bars/sections/meter.
- Key ring, home key, register bounds.
- Harmony weights, borrowed chords, Viterbi.
- Guitar pattern/profile, ngón tay, dây, giọng (chỉ chịu ảnh hưởng gián tiếp qua `tempo`).
- AI tạo profile.
- Profile server theo user, auth, quota.
- So sánh DFI xuyên profile.
- A/B nghe song song (V1.1).

---

## 4. Data model

### 4.1 Profile

```json
{
  "schema": 2,
  "id": "default",
  "name": "Default",
  "params": {
    "tempo": 1.0,
    "humanize": 1.0,
    "breath": 1.0,
    "dynamics": 1.0,
    "color": 1.0,
    "noise": 0.1,
    "density": 1.0
  },
  "createdAt": null,
  "updatedAt": null
}
```

- `Default`: `id = "default"`, bất biến, `createdAt/updatedAt = null`.
- Profile người dùng: `id` sinh local, `name` đổi được, `params` đã chuẩn hoá.
- **Hash chỉ tính trên `schema + params`**, không tính `id`, `name`, thời gian. Hai profile khác tên nhưng cùng parameter dùng chung cache audio.

### 4.2 Canonical hash

```text
params = { key: round(round(value / step) * step, 2) for key in SCHEMA }
canonical = json.dumps(
  {"schema": 2, "params": params},
  separators=(",", ":"),
  sort_keys=True,
)
params_hash = sha256(canonical).hexdigest()[:12]
```

- **Round theo step trước khi hash.** Nếu không, `0.9600000000000001` tạo hash khác `0.96` dù nghe giống hệt.
- `round(..., 2)` để xoá bụi float sau khi nhân step.
- Server là nơi tính hash chuẩn. Client dùng `paramsKey` (canonical string) cho React key; không tự hash.
- Default hash được pin trong test. Với canonical ở §4.1: `5800e09635be`.

### 4.3 Preset built-in

| Tên | Ý tưởng | Params gợi ý |
|---|---|---|
| `Default` | Đúng bản đang nghe | tất cả `1.0` |
| `Gần` | Khô, rõ, ít không gian | `color 0.45`, `noise 0.0` |
| `Ấm` | Nhiều thân tiếng, chậm hơn một nhịp | `tempo 0.96`, `color 1.0`, `noise 0.2` |
| `Sống` | Nhiều humanize và hơi thở | `humanize 1.1`, `breath 1.15` |
| `Dày` | Nhiều fill/bell hơn | `density 1.25` |

Preset chỉ là điểm bắt đầu; người dùng vẫn sửa và lưu thành profile riêng.

Preset chỉ chứa knob đã ship. `dynamics` và `density` thuộc A2, nên preset dùng chúng (`Dày`) chỉ mở sau Phase 1B; trước đó chúng sẽ tạo hash khác mà audio y hệt. `Gần` vì vậy chỉ còn `color` và `noise`.

---

## 5. Backend contract

### 5.1 Một nguồn sự thật cho schema

`backend/app/sonify/params.py` là nguồn duy nhất:

- `DEFAULT_PARAMS`
- `PARAM_SCHEMA` (key, label, group, min, max, step, default, unit, description)
- `normalize_params`
- `params_hash`
- `compose_params` (ContextVar, theo pattern `form.py:137`, `groove.py:31`)

Một script build `scripts/gen_params_schema.py` sinh ra:

- `backend/app/sonify/fixtures/params_schema.json`
- `src/musicalize/paramsSchema.generated.ts`

CI so sánh output với file đã commit; lệch thì fail. Không có bản fallback viết tay thứ ba. App boot offline đọc file generated đã bundle.

`GET /v1/sonify/params/schema` trả:

```json
{
  "schema": 2,
  "groups": [
    {
      "id": "performance",
      "label": "Trình diễn",
      "fields": [
        {
          "key": "tempo",
          "label": "Nhịp",
          "type": "number",
          "min": 0.75,
          "max": 1.25,
          "step": 0.01,
          "default": 1.0,
          "unit": "×",
          "description": "Nhân BPM gốc của dòng nhạc."
        }
      ]
    },
    {
      "id": "texture",
      "label": "Sâu hơn",
      "fields": [
        { "key": "dynamics", "label": "Tương phản" },
        { "key": "noise", "label": "Nhiễu" },
        { "key": "density", "label": "Mật độ" }
      ]
    }
  ],
  "defaultHash": "5800e09635be",
  "enabled": true
}
```

`enabled` là kill switch server-side. Khi `false`, client ẩn/disable nút `Tinh chỉnh` và không gửi `p`; server cũng bỏ qua `p` và trả Default. Nhờ vậy UI không hiển thị profile trong khi tai nghe Default.

Hai nhóm khớp disclosure “Sâu hơn” ở UI; nhóm `performance` chứa `tempo`, `humanize`, `breath`, `color`. Các field nhóm `texture` ở ví dụ trên lược bớt `min/max/step/default` cho gọn; schema thật có đủ, sinh từ `params.py`.

### 5.2 Validate

`POST /v1/sonify/params/validate`

Request:

```json
{ "schema": 2, "params": { "tempo": 1.4, "humanize": 99 } }
```

Response:

```json
{
  "schema": 2,
  "params": { "tempo": 1.25, "humanize": 2.0, "breath": 1.0, "dynamics": 1.0, "color": 1.0, "noise": 0.1, "density": 1.0 },
  "hash": "…",
  "warnings": [
    { "code": "clamped", "key": "tempo", "value": 1.4 },
    { "code": "clamped", "key": "humanize", "value": 99 }
  ]
}
```

Quy tắc:

- Thiếu key → lấy default.
- Key lạ → bỏ qua và cảnh báo `unknown_key`.
- Sai kiểu → 400.
- Số ngoài khoảng → kẹp và cảnh báo `clamped`.
- Cảnh báo mềm `high_humanize`, `high_breath`. Ghi chú guitar “dưới ngưỡng tremolo” là hint phía client, suy từ `baseBpm` trong schema và BPM hiệu lực < 90; server không nhận `variant` ở `/validate` nên không phát warning này.
- **Warnings trả `code + key + value`, không trả câu tiếng Việt.** Client map sang copy; server không phải nguồn bản địa hoá.
- Không nhận chuỗi FFmpeg, code, biểu thức, đường dẫn file, key ngoài schema.

### 5.3 Preset

`GET /v1/sonify/params/presets` trả danh sách preset built-in. Không cần auth.

### 5.4 Audio, peaks và mọi đường phụ thuộc params

Một query parameter duy nhất:

```text
p=<base64url(canonical params JSON)>
```

- Default: bỏ trống `p`, hoặc `p` giải mã ra đúng default.
- Legacy `humanize=0` / `color=0` vẫn nhận và map vào params:
  - `humanize=0` → `{humanize: 0, breath: 0}` — bản cũ bỏ hẳn `humanize()`, nên phải tắt cả tempo clock; xem §6.1
  - `color=0` → `params.color = 0`
- `p` giới hạn 2048 ký tự, validate trước khi render.
- `p` sai: `400` với thông báo rõ. UI luôn validate trước khi gọi audio.

Không chỉ audio: **peaks và scrubber phải xin cùng params**, nếu không biên độ hiển thị lệch với tiếng:

| Đường | Hiện tại | Phải thêm |
|---|---|---|
| `RecapAsset.audio_url` | `humanize`/`color` | `p` |
| `movement_audio_path()` (`services/spans.py:75`) | `layer_query` | `p` |
| `mixQuery()` (`src/api/client.ts:549-552`) | `&humanize=&color=` | `p` (hoặc default) |
| `fetchSpanPeaks()` (`client.ts:701`) | dùng `mixQuery` | tự động theo |
| Recap peaks | dùng `mixQuery` | tự động theo |
| `/sonify/dfi/pieces` | không có | `p` |

`mixQuery` đổi thành `paramsQuery(params)`; `SonifyMix` được thay bằng `params`. Không giữ hai cơ chế song song.

Ví dụ canonical đầy đủ cho `tempo = 0.96`:

```text
{"params":{"breath":1.0,"color":1.0,"density":1.0,"dynamics":1.0,"humanize":1.0,"noise":0.1,"tempo":0.96},"schema":2}
```

```text
p=eyJwYXJhbXMiOnsiYnJlYXRoIjoxLjAsImNvbG9yIjoxLjAsImRlbnNpdHkiOjEuMCwiZHluYW1pY3MiOjEuMCwiaHVtYW5pemUiOjEuMCwibm9pc2UiOjAuMSwidGVtcG8iOjAuOTZ9LCJzY2hlbWEiOjJ9
```

---

## 6. Cache, revision, DFI

### 6.1 Cache mark là hàm thuần của params

Không để query quyết định tên file. Normalize trước, rồi mới chọn mark:

```python
def cache_mark(params) -> str:
    p = normalize_params(params)
    if p == DEFAULT_PARAMS:
        return ""                       # cache cũ, không đổi tên
    return legacy_layer_mark(p) or f"_p{params_hash(p)}"
```

`legacy_layer_mark` chỉ nhận **đúng** các tổ hợp cũ, mọi knob khác phải là `1.0`:

| params | mark | Vì sao |
|---|---|---|
| `humanize 0, breath 0, color 1` | `_nh` | bản cũ bỏ hẳn `humanize()`: không offset, không tempo clock, không `_clamp_guitar` |
| `humanize 1, breath 1, color 0` | `_nc` | bản cũ vẫn humanize đầy đủ, chỉ bỏ preset |
| `humanize 0, breath 0, color 0` | `_nh_nc` | cả hai lớp tắt |
| mọi tổ hợp khác | `_p<hash>` | kể cả `humanize 0` với `breath 1` |

Điểm quan trọng: **`breath` phải đi cùng `humanize` trong điều kiện legacy.** Code cũ bỏ toàn bộ `humanize()` khi `humanize=False` (`audio.py:1372`, `:1555`), nên file `_nh` trên đĩa **không có tempo clock**. Nếu `h=0` chỉ đặt `humanize=0` mà để `breath=1`, `humanize()` vẫn chạy và sinh tempo event → audio khác file `_nh` đang có.

Vì vậy:

- Legacy query `h=0` map thành `{humanize: 0, breath: 0}`.
- Dispatch: chỉ gọi `humanize()` khi `humanize != 0` **hoặc** `breath != 0`. Khi cả hai bằng 0, bỏ hẳn lời gọi, đúng như bản cũ (không `_copy_ties`, không `_clamp_guitar`).
- Khi `humanize = 0` nhưng `breath > 0`: vẫn gọi để lấy tempo clock. Lưu ý `offsets` **không rỗng**: code hiện `setdefault` cho mọi movable run, kể cả khi giá trị clamp ra 0 (`humanize.py:89-92`). Vì vậy guard phải là `if any(offsets.values()):`, hoặc bỏ `setdefault` khi `humanize == 0`. `if offsets:` là **sai** và vẫn kéo velocity guitar 65–68 lên 69 (`humanize.py:312`).
- `p{humanize: 0}` (breath vẫn `1.0`) là bản **khác**: có tempo clock, không offset, và dùng `_p<hash>`.
- `p{humanize: 0, breath: 0}` dùng đúng `_nh`, không sinh thêm file.

Metadata luôn ghi `paramsHash`, `params`, `profileName` (nếu có).

### 6.2 Revision và `prune()` — blocker Phase 0

- `RECAP_REVISION` / `SPAN_REVISION` **không tăng** khi người dùng đổi profile.
- `_STORED_NAME` (`audio.py:55-62`) phải nhận thêm `_p[0-9a-f]{12}` **trước khi** bất kỳ audio non-default nào được ghi.
- `prune()` (`audio.py:1170-1178`) xoá mọi file không khớp regex và chạy trong mỗi `get()`. Nếu quên regex, profile đầu tiên render xong sẽ bị xoá ngay lần `get()` kế tiếp.
- `_prune_spans()` dùng substring `_{variant}_{SPAN_REVISION}_`, nên `_p<hash>` ở cuối vẫn an toàn; vẫn phải có test.
- Test bắt buộc: ghi một file `_p…` rồi gọi `prune()`, file còn; file revision cũ bị xoá.

### 6.3 Giới hạn cache — LRU theo hash

Không thể giữ mọi `params_hash` 30 ngày: mỗi render là một MuseScore, không gian knob là vô hạn.

Chốt:

- **Pin**: Default (`""`) và legacy `_nh/_nc/_nh_nc` không bị LRU, chỉ bị xoá theo tuổi `AUDIO_MAX_AGE_DAYS`.
- **Non-default**: giữ tối đa `VSTOCK_PARAMS_CACHE_MAX` hash gần nhất cho mỗi `piece + layer` (mặc định `4`), xoá theo `mtime` cũ nhất trước.
- LRU chạy trong `prune()` cùng lượt quét hiện có, không thêm I/O đáng kể.
- Metadata sidecar của DFI prune theo cùng khoá.

Prune theo tuổi vẫn giữ 30 ngày cho mọi file còn lại.

Lưu ý: hash tính trên **hệ số `tempo`**, trong khi audio phụ thuộc `int(bpm × tempo + 0.5)`. Vì profile áp cho mọi variant, không thể canonical hoá hash theo BPM hiệu lực; hai `tempo` sát nhau có thể cho cùng audio nhưng hai hash. LRU đếm riêng từng hash — chấp nhận trong V1, không có cách gộp đúng nếu chưa biết variant.

### 6.4 DFI — cả đường audio lẫn đường recompose

DFI hiện được compose lại ngoài audio qua `dfi_service.recap_dfi(...)` (`services/sessions.py:246`). Key cache `_recap_key` / `_movement_key` (`services/dfi.py:145-175`) chỉ có `RC_REV + DFI_VERSION + digest + variant + ensemble + humanize + color`. Thiếu `params_hash` thì DFI của profile khác **ghi đè** DFI Default cùng piece.

Chốt: **giữ `dfi_inputs = digest`**, thêm field riêng `dfiParamsHash`. Không đổi format `dfi_inputs` thành `digest:hash`, vì `sessions.py:236` và `spans.py:281/:331` đang so `dfi_inputs != digest`; đổi format sẽ làm **mọi** asset cũ mismatch và recompose score toàn corpus một lần dù audio không đổi.

Phải sửa cả năm chỗ:

1. `_recap_key` / `_movement_key` nhận thêm `params_hash` **chỉ khi** `cache_mark` là `_p<hash>`. Default và legacy `_nh/_nc/_nh_nc` giữ đúng tuple cũ, nên sidecar DFI cũ vẫn dùng; không recompose oan.
2. Thêm field `dfiParamsHash` vào asset/metadata; `dfi_inputs` giữ nguyên `digest`.
3. `sessions.py:236` so `digest` **và** `dfiParamsHash`.
4. `spans.py:281` và `spans.py:331` cũng so cả hai. Bỏ sót span thì DFI của movement vẫn dùng bản cũ và ghi đè nhau ở bucket `span`, dù recap đã đúng.
5. `/v1/sonify/dfi/pieces` nhận `p` và compose theo params; metadata DFI ghi `paramsHash` để debug.

### 6.5 Corpus signature

- DFI score của bản non-default vẫn được tính và lưu.
- **Cột so sánh corpus chỉ hiện với Default trong V1.** DFI của hai profile khác nhau không so sánh được với cùng một median.
- `dfi/signatures` **không** nhận `p`. Endpoint hiện đọc fixture `backend/app/sonify/fixtures/dfi_signatures.json` — file này **chưa tồn tại**, nên endpoint đang trả `[]`. V1 giữ nguyên; UI chỉ cần ẩn marker khi params ≠ default.
- `Controls.tsx` đã tách `dfiSignature` sẵn, nên việc ẩn marker là một điều kiện, không phải refactor.
- Khi default đổi hành vi: tăng `DFI_VERSION` nếu công thức đổi; nếu chỉ đổi âm thanh thì không.

---

## 7. Lưu profile

### 7.1 V1 — local profile

Vì chưa có auth:

- `Default` và preset built-in: server.
- Profile người dùng: **AsyncStorage**, key `vstock.musicalize.profiles.v1`.

```json
{
  "schema": 2,
  "activeId": "default",
  "profiles": [
    { "id": "default", "name": "Default", "params": { "...": 1.0 } },
    { "id": "p_ab12", "name": "Ấm tối", "params": { "...": 0.96 } }
  ]
}
```

Quy tắc:

- `Default` không sửa, không xoá. Muốn chỉnh thì “Nhân bản”.
- Tên không rỗng, tối đa 40 ký tự; không trùng (không phân biệt hoa thường), nếu trùng thêm hậu tố.
- Đổi tên chỉ đổi `name`, không đổi `params`, không đổi hash.
- Xoá profile đang dùng → quay về `Default`.
- “Reset” ở tab Tinh chỉnh bỏ draft, quay về profile đang chọn; “Về Default” ở tab Profile đưa params profile về default nhưng giữ tên.
- Import/export JSON qua clipboard (web và native). V1 chưa cần file picker.

### 7.2 Khi có auth (sau này)

- Chuyển profile lên server, giữ nguyên schema và hash.
- Local profile có thể sync lên.
- Chưa làm trong V1.

---

## 8. UI/UX

### 8.1 Cá tính app

Musicalize là một **phòng nghe**, không phải DAW:

- Nền tối, đường kẻ mảnh, chữ nhỏ, đồng hồ mono.
- Điều khiển hiện tại giống mặt máy: shelf thể loại, hàng ensemble, transport tròn.
- Ít nút, ít chữ, ưu tiên nghe.

Bàn tinh chỉnh nên giống **mở nắp một nhạc cụ**: chỉ hiện khi cần, gọn, có nhãn mono, không chiếm chỗ thường trực.

### 8.2 Một nút mở, hai cách trình bày

Không mở inline: inline làm dock cao lên, đẩy chart và transport xuống, buộc scroll — đúng hạn chế cần tránh. Bàn tinh chỉnh là **lớp phủ có chủ đích**, mở ra rồi đóng lại, không đổi bố cục thường trực.

Nút gear hiện tại được thay bằng nút mở trong `shelfRow` sẵn có:

```text
[ Symphony ] [ Jazz ] [ Minimalist ] [ Ambient ] [ Guitar ]
Wood  Brass          DFI   Tinh chỉnh · Default  ›
                            ▶  ↻  🔊  0:00 / 2:00
```

- Không thêm hàng mới: dock wide cố định `DOCK_HEIGHT = 232`, thêm hàng sẽ tràn.
- Nút có `maxWidth` khoảng 220 px, `flexShrink: 1`, `numberOfLines={1}`, ellipsis cho tên profile tới 40 ký tự.
- Ở 960 px, chỗ còn lại sau cột trái `COLUMN_WIDTH = 312` là 648 px cho 5 tile + ensemble links + DFI + nút; phải test ở 960 và 1280, không chỉ ở desktop rộng.
- Trên narrow, nút được phép wrap xuống dòng trong dock (dock narrow đã `height: 'auto'`). Trên wide **không wrap** vì dock cố định chiều cao sẽ bị clip.

| Màn hình | Cách mở |
|---|---|
| `wide` ≥ 960 px | Drawer trượt từ cạnh phải, rộng 360–420 px. Ở ≥ 1280 px drawer **push** nhẹ để chart reflow; ở 960–1279 px drawer **overlay** mép phải chart. |
| `narrow` < 960 px | Bottom sheet từ dưới lên, snap 48% và 88% chiều cao. Chart vẫn thấy ở nửa trên khi ở snap thấp. |

Quy tắc chung:

- **Không backdrop tối toàn màn hình**; chỉ lớp trong suốt bắt tap ra ngoài.
- Drag handle để đóng; web `Esc` đóng.
- Nội dung dài scroll **bên trong** drawer/sheet.
- `TuningPanel` là một component duy nhất; khác container và hướng animation.
- Transport và chart không unmount; audio tiếp tục phát.
- State profile (`activeId`, `params`, danh sách đã lưu) nằm ở **`MusicalizeApp`**, nơi chỉ render một room tại một thời điểm (`MusicalizeApp.tsx:30-32`), rồi truyền xuống qua context. Không đặt hook riêng trong `LiveRoom` và `ReplayRoom` để tránh hai bản state lệch nhau.
- `TuningPanel` vẫn render **một lần trong `RoomFrame`** từ context đó; trigger nằm trong `Controls`. Panel không unmount khi đổi room vì app chỉ có một room active.
- `Esc` đi qua `useKeyboard` sẵn có của `ReplayRoom`: thêm `tuningOpen` vào điều kiện `!paletteOpen && !optionsOpen`, không đăng ký listener thứ hai.

### 8.3 Nội dung drawer/sheet

Hai tab:

```text
[ Tinh chỉnh ]  [ Profile ]
```

Tab `Tinh chỉnh`:

Mỗi thanh trượt có hai mốc tách biệt: vạch mảnh ở **giữa thang** và mỏ neo đậm tại **giá trị default** (có thể lệch, ví dụ `noise`). Phần tô màu chạy từ mỏ neo đến knob; nút `?` cạnh nhãn mở một câu mô tả.

```text
Default  • đã sửa
[−] Nhịp        ──────◆────  1.00×  (90 BPM) [+]
[−] Người       ────◆──────  1.00          [+]
[−] Hơi thở     ────◆──────  1.00          [+]
[−] Màu         ─────■◆────  1.00          [+]

── Sâu hơn ─────────────────
[−] Tương phản  ──────◆────  1.00          [+]
[−] Nhiễu       ◆──────────  0.10%         [+]
[−] Mật độ      ────◆──────  1.00          [+]

[Reset]                         [Lưu]
```

Tab `Profile`:

- Danh sách profile: `Default` (khoá), các profile local.
- Tạo mới, nhân bản, đổi tên, xoá, reset về Default.
- Import/export JSON.
- Chọn profile chỉ đổi profile đang dùng; **không tự phát**.
- Không có A/B trong V1; nếu làm, ghi rõ `(V1.1)` và không đưa vào AC V1.

Hành vi:

- Kéo slider hoặc bấm `−/+` chỉ cập nhật **draft**, không render audio, không đổi URL.
- `Reset` bỏ thay đổi chưa lưu, quay draft về profile đang chọn.
- `Lưu` ghi draft vào profile; không phát lại, không dừng audio đang chạy.
- Nút Play bên ngoài dùng profile đã lưu mới nhất: params giống bản đang nghe thì dùng lại cache, khác thì soạn bản mới.
- Nếu draft đang khác profile, Play tự lưu draft trước (Default sẽ thành bản sao có tên), rồi phát cấu hình đó.
- Hiển thị BPM suy ra cạnh `Nhịp` (ví dụ `1.00× · 90 BPM`); guitar dưới 90 BPM hiện ghi chú “dưới ngưỡng tremolo”.
- Cảnh báo mềm `humanize > 1.1`, `breath > 1.2`, không chặn.
- Haptic nhẹ khi chạm mốc (`expo-haptics` đã có), không rung liên tục khi kéo.
- Không còn nút “Nghe bản này” trong drawer/sheet.

### 8.4 Kỹ thuật và a11y

- Dùng `Modal` trong suốt + `Animated`/Reanimated cho translateX/translateY. Không cần thêm dependency: `react-native-reanimated` và `react-native-gesture-handler` đã có.
- `wide`: container `position: absolute; right: 0; top: 0; bottom: 0; width: 380`. Push mode đặt drawer trong hàng flex với stage và animate width; chỉ bật push ở `width >= 1280`.
- `narrow`: container `position: absolute; left/right/bottom: 0`, chiều cao theo snap point, có safe-area inset.
- Không dùng `Modal` full-screen `animationType="slide"` trên điện thoại vì nó che toàn bộ chart.
- Slider có `accessibilityRole="adjustable"`, `accessibilityValue={{ min, max, now, text }}`, `accessibilityActions` tăng/giảm theo step; arrow keys trên web; focus ring dùng `installFocusRing()` sẵn có trong `a11y.ts`.
- Khi drawer mở, `optionsOpen` vẫn bật để room nhả phím tắt transport, giống `OptionsPopover`.

### 8.5 Vì sao không chọn phương án khác

| Phương án | Vì sao không chọn |
|---|---|
| Inline ngay dưới controls | Đẩy chart/transport xuống, buộc scroll, mất ngữ cảnh đang xem chart. |
| Sidebar parameter thường trực | Chiếm chỗ, biến phòng nghe thành DAW. |
| Màn Settings riêng | Phải rời ngữ cảnh đang nghe; chậm thử. |
| Chỉ popover nhỏ như hiện tại | Không đủ chỗ cho 7 knob + profile. |
| Modal toàn màn hình | Che chart và transport; mất cảm giác “đang nghe”. |
| Bottom sheet trên mọi màn | Trên web rộng, drawer phải tận dụng chiều ngang và giữ chart gần như nguyên vẹn. |

---

## 9. URL và chia sẻ

### 9.1 Format

- Default: giữ URL cũ, không có `p`.
- Profile khác: thêm `p=<base64url(canonical params)>`, không padding.
- Legacy `h` / `c` vẫn đọc được.
- `p` chỉ chứa params, không chứa tên profile.

### 9.2 Round-trip

- `parseLink()` trả `params` đã chuẩn hoá (hoặc `null` = default).
- Link cũ `h=0` map thành `{humanize: 0, breath: 0}`; `c=0` thành `{color: 0}`, để vẫn trỏ đúng `_nh/_nc/_nh_nc`.
- `writeLink()` ghi `p` khi khác default, bỏ `p` khi default. Khi mở link legacy rồi ghi lại, **chuyển** `h/c` sang `p` và bỏ `h/c`; không giữ hai cách biểu diễn cùng một params.
- `p` hỏng hoặc quá dài: fallback Default, không làm sập phòng nghe.
- Không đưa `paramsHash` vào URL; server tính lại từ `p`.
- Cùng một params luôn cho cùng canonical string: round theo step trước khi encode.

### 9.3 A/B (V1.1)

- A = snapshot params đang phát; B = params đang chỉnh.
- Chuyển bằng nút nhỏ cạnh transport; giữ vị trí phát.
- Không nằm trong AC V1; chỉ làm nếu Phase 3 còn thời gian.

---

## 10. Validation, an toàn, rollout

- Không nhận chuỗi FFmpeg, code, biểu thức, đường dẫn file từ client.
- Chỉ nhận đúng 7 key, đúng kiểu số.
- Kẹp theo khoảng; cảnh báo dạng `code + key`.
- Giới hạn độ dài `p` (2048) và kích thước JSON.
- Rate limit render dùng slot MuseScore hiện có; cảnh báo khi client tạo quá nhiều params trong thời gian ngắn.
- Cache: LRU theo hash (§6.3), không giữ vô hạn.
- Log `params_hash`, `variant`, `ensemble`, thời gian render.
- **Kill switch**: `VSTOCK_SONIFY_PARAMS=0` buộc server bỏ qua `p`, trả Default và set `enabled: false` trong `/params/schema`. Client đọc cờ này và ẩn/disable nút `Tinh chỉnh`, không chỉ dựa `EXPO_PUBLIC_SONIFY_PARAMS`. Nhờ vậy không có cảnh UI hiện profile A trong khi tai nghe Default.
- Client fallback `EXPO_PUBLIC_SONIFY_PARAMS=0` vẫn giữ để tắt trước khi gọi schema, nhưng cờ server là nguồn quyết định cuối.
- Rollout: bật server trước (chấp nhận `p`), đo parity; sau đó bật client. Khi tắt, cả hai đầu cùng về Default.

---

## 11. Test và tiêu chí nghiệm thu

### 11.1 Backend

`test_params.py` — **file mới**:

- Default canonical JSON và hash `5800e09635be` ổn định.
- Round theo step trước khi hash: `0.9600000000000001` và `0.96` cùng hash.
- Schema đúng default/min/max/step, đủ hai nhóm.
- Normalize: thiếu key → default; ngoài khoảng → kẹp; key lạ → `unknown_key`; sai kiểu → lỗi.
- Encode/decode `p` round-trip.
- `cache_mark` chỉ trả `_nh/_nc/_nh_nc` cho đúng tổ hợp legacy; mọi tổ hợp khác trả `_p<hash>`.

`test_tempo.py` — **file mới**:

- `tempo = 1` khớp BPM gốc từng variant.
- `tempo = 0.9` đổi BPM và độ dài đúng.
- BPM hiệu lực là **int**: `torroba` ở `0.9` cho `86`, `<per-minute>` là `"86"`.
- Half-up, không banker's: BPM 90 ở `tempo 0.85` cho `77`, ở `0.95` cho `86`.
- `torroba` ở `0.9` → **không tremolo**; writer nhận `ctx.bpm` hiệu lực, không phải BPM danh nghĩa.
- `classic`/`guitar_sor` ở Default 88 vẫn không tremolo.

`test_humanize.py` — **file đã có, mở rộng**:

- `humanize = 1` khớp tuyệt đối offset hiện tại.
- `humanize = 0` không offset.
- `humanize = 1.05` khác `1.0` ở cả nhánh `base ±2` (kiểm tra phân bố offset, không chỉ một nốt).
- `chosen_offset` ổn định giữa process: chạy lại với `PYTHONHASHSEED` khác nhau, offset giống hệt; bit làm tròn lấy từ FNV `value`, không từ `hash()`.
- `FREEZE_GAP` không đổi khi humanize đổi.
- `breath = 0` không tempo event; `breath = 1` khớp hiện tại.
- `breath = 1.5` lệch nhiều hơn `1.0` trên variant còn dư trần; Torroba ghi nhận bão hoà.
- **Legacy `_nh`**: `h=0` và `p{humanize:0, breath:0}` cho MusicXML **giống từng byte**, và giống snapshot trước khi tách params.
- `humanize = 0, breath = 1` không đổi velocity guitar: `offsets` có key nhưng toàn 0, guard phải là `any(offsets.values())`, không phải `if offsets:`.

`test_color.py` — **file mới**:

- `amount = 1` sinh đúng từng byte chuỗi Default cho cả 5 variant.
- `amount = 0` không filter màu.
- `amount = 0.5` giảm gain/decay theo spec, threshold lerp đúng.

`test_dynamics.py` — **file mới**:

- `dynamics = 1` khớp bảng hiện tại.
- `sound_for` suy từ `velocity_for` (`round(vel/90*100)`).
- Không module nào ngoài `dynamics.py` import trực tiếp `SOUND` / `PIANO_VELOCITY`.
- Ghép `dynamics 1.5 × humanize 1.5` không làm vỡ freeze/repair.

`test_params_cache.py` — **file mới** (tên này để không lẫn với `test_ensemble.py` đang chứa test stem/layer):

- Default giữ nguyên stem.
- `h=0` và `p{humanize:0, breath:0}` cho **cùng** tên `_nh`; `p{humanize:0}` (breath 1) cho `_p<hash>`.
- Profile khác default sinh `_p<hash>`.
- Hai profile cùng params khác tên dùng chung file.
- **Prune giữ file `_p…` vừa ghi**; file revision cũ bị xoá.
- LRU giữ đúng `VSTOCK_PARAMS_CACHE_MAX` hash, xoá mtime cũ nhất, không đụng Default/legacy.

`test_dfi.py` — **file đã có, mở rộng**:

- `params_hash` có trong `_recap_key`/`_movement_key` chỉ với bản `_p<hash>`; Default/legacy giữ tuple cũ.
- `dfi_inputs` vẫn là `digest`; `dfiParamsHash` là field riêng và được so ở cả recap (`sessions.py:236`) lẫn span (`spans.py:281`, `:331`).
- Asset cũ không có `dfiParamsHash` không bị recompose chỉ vì đổi format.
- Hai profile khác params không ghi đè DFI của nhau, kể cả bucket `span`.
- `/dfi/pieces` với `p` trả DFI của đúng params.
- Signature không nhận `p`; UI ẩn marker khi params ≠ default.

**Default parity**: render một bộ input cố định với Default, so score + MusicXML với snapshot trước khi tách params.

### 11.2 Frontend

`params.test.ts` (phải thêm vào script `test:musicalize` trong `package.json:51`):

- Default params, encode/decode, legacy `h/c`.
- Round theo step trước khi encode.
- Profile CRUD local: tạo, đổi tên, nhân bản, xoá, reset; tên trùng.
- Client chỉ dùng `paramsKey` canonical string, không có `cacheMark`; hash do server tính.

`link.test.ts`:

- `p` round-trip.
- `p` hỏng/quá dài fallback Default.
- Link cũ vẫn hoạt động; mở `h=0`/`c=0` rồi `writeLink()` chuyển sang `p`, không còn `h/c`.
- `p` xuất hiện ở audio URL **và** peaks URL.

UI:

- Điện thoại: bottom sheet snap 48%/88%; chart thấy ở nửa trên; transport không bị đẩy khỏi màn hình.
- Web 960 px và 1280 px: nút `Tinh chỉnh · Default` không tràn, tên dài ellipsis; drawer overlay/push đúng ngưỡng.
- Không backdrop tối; tap ngoài và `Esc` đóng.
- Mỗi slider có nút `−`/`+` hai đầu, nhảy đúng step và disable ở biên.
- Kéo slider hoặc bấm `−/+` chỉ đổi draft; không render, không đổi URL.
- `Lưu` ghi draft vào profile, không phát lại; `Reset` bỏ draft về profile đang chọn.
- Nút Play bên ngoài dùng profile đã lưu mới nhất; nếu draft chưa lưu, Play tự lưu draft trước; params không đổi thì dùng cache cũ, đổi thì soạn bản mới.
- Chọn profile không tự phát; không còn nút “Nghe bản này” hay “Dùng profile này”.
- Slider có role `adjustable`, arrow keys hoạt động.

### 11.3 Tiêu chí nghiệm thu

**Backend (V1 bắt buộc)**

1. Default cho ra score/MusicXML **y hệt** trước khi tách params; test cũ pass; `h=0` cho MusicXML giống bản legacy `_nh` (file audio cũ có thể đã bị `prune()` khi revision tăng). Audio Default đổi một lần ở revision 80 do bed noise phủ cả 5 variant; ghi nhận và nghe thử piano/ambient.
2. Bảy knob có hiệu lực qua `p`; `tempo` áp trước writer; BPM hiệu lực là int; tremolo rơi đúng ngưỡng.
3. Legacy `h=0` cho **MusicXML từng byte** giống `p{humanize:0, breath:0}` và giống `_nh` cũ; `p{humanize:0}` là bản khác.
4. Không có cache collision; `prune()` không xoá bản non-default; LRU bounded.
5. DFI của profile khác không ghi đè DFI Default, ở cả recap lẫn span.
6. `p` round-trip; legacy `h/c` vẫn chạy.

**V1 UI (bắt buộc)**

7. Tạo profile có tên, đổi tên, nhân bản, xoá, reset; restart app vẫn còn.
8. URL chia sẻ mở lại đúng parameter.
9. Drawer/sheet dùng được trên web và điện thoại, không che transport, không bắt scroll chart.

**V1.1 (không chặn)**

10. A/B nghe song song.
11. Quản lý profile nâng cao, import/export hàng loạt.

---

## 12. Phân kỳ công việc

| Phase | Việc | Kết quả |
|---|---|---|
| **0. Nền + an toàn cache** | `params.py`, schema generated, default hash, `compose_params`, `cache_mark`, sửa `_STORED_NAME`, dispatch skip `humanize()`, guard `_clamp_guitar`, test prune + legacy parity | Chưa đổi âm thanh; không mất file; `_nh` cũ vẫn đúng |
| **1A. Performance + mix** | Nối `tempo` (int, trước writer), `humanize` (tách freeze, stochastic round), `breath`, `ColorSpec`, `noise` | 5 knob hoạt động qua API |
| **1B. Texture** | Nối `dynamics` (hàm suy ra), `density` | Đủ 7 knob |
| **2. Cache + DFI + URL** | LRU, DFI keys (recap + span), `p` cho audio/peaks/dfi, legacy map | Không phát nhầm cache; chia sẻ được |
| **3. UI** | State ở `MusicalizeApp`, `TuningPanel` trong `RoomFrame`, drawer/sheet, tab `Profile`, local profile, a11y | Người dùng tự chỉnh và lưu |
| **4. Sau V1** | A/B, tầng B/C, profile server, auth, AI sinh JSON | Để sau |

Ưu tiên khi thời gian hẹp:

1. Phase 0 + 1A + 2 (backend đúng, an toàn dữ liệu, chia sẻ được).
2. Phase 3 tối giản: nút mở + drawer/sheet + lưu profile.
3. 1B.
4. A/B (V1.1).

---

## 13. Rủi ro và cách giảm

| Rủi ro | Cách giảm |
|---|---|
| Default lệch tiếng | Snapshot score/MusicXML; test parity; không tăng revision nếu không cần; kill switch server. |
| `tempo` làm rơi tremolo ngoài ý muốn | Dùng BPM hiệu lực cho writer; test từng ensemble; UI báo dưới ngưỡng 90. |
| BPM int làm tempo thô | Chấp nhận; UI hiện BPM suy ra; test `<per-minute>` là int. |
| `humanize` đổi cấu trúc freeze | Tách `FREEZE_GAP` khỏi `offset_cap`; stochastic round, không `int()`; test 1.0 parity và 1.05 khác ở nhánh ±2. |
| Legacy `_nh` phát sai tiếng | `h=0` map `{humanize:0, breath:0}`; skip `humanize()` khi cả hai 0; guard `_clamp_guitar`; test MusicXML byte. |
| `prune()` xoá audio mới | Sửa regex Phase 0; test prune trước khi render profile đầu tiên. |
| DFI profile ghi đè Default | Hash vào key chỉ khi `_p<hash>`; `dfiInputs` giữ digest, thêm `dfiParamsHash`; so ở cả recap lẫn span. |
| Đổi format `dfi_inputs` làm recompose toàn corpus | Giữ `dfi_inputs = digest`; thêm field riêng. |
| `dynamics`/`density` chạm nhiều module | A2; thay dict bằng hàm; test cấm import dict; test ghép humanize. |
| ContextVar rò rỉ giữa request | `compose_params` context manager, reset trong `finally`; `asyncio.to_thread` copy context. |
| Global `FormSpec` bị sửa | Luôn `replace(spec, bpm=...)`. |
| Cache phình | LRU theo hash; pin Default/legacy; hash 12 ký tự. |
| `p` chỉ đổi audio, không đổi peaks | `paramsQuery` dùng chung cho audio, peaks, movement, dfi pieces. |
| Nút mở tràn ở 960 px | `maxWidth`, `flexShrink`, ellipsis; test 960 và 1280. |
| UI quá giống DAW | Track mảnh, nhãn mono, không sidebar; chỉ mở khi cần. |
| Slider render liên tục | Slider/`−/+` chỉ đổi draft; Play mới dùng profile đã lưu và cache hash quyết định bản cũ/mới. |
| Tên profile trùng | Chuẩn hoá, cảnh báo, thêm hậu tố. |

---

## 14. Việc cần làm ngay khi bắt tay

1. Tạo `params.py` với `DEFAULT_PARAMS`, `PARAM_SCHEMA`, `normalize_params`, `params_hash`, `cache_mark`, `compose_params`.
2. Sửa `_STORED_NAME` + test `prune()` giữ `_p…` **trước** khi render bất kỳ profile nào.
3. Thêm dispatch skip `humanize()` khi `humanize = 0` và `breath = 0`; guard `_clamp_guitar` bằng `any(offsets.values())` (không dùng `if offsets:`).
4. Viết test legacy `h=0` vs `p{humanize:0, breath:0}`: MusicXML từng byte; test default parity.
5. Sinh schema generated + CI diff.
6. Nối `tempo` (int, trước writer, test tremolo) và `humanize` (tách freeze, stochastic round).
7. Nối `breath` và `ColorSpec`/`noise`.
8. Làm `p` + cache hash + legacy map cho audio **và** peaks.
9. Thread hash vào DFI key + `dfiParamsHash` (recap + span); giữ `dfi_inputs = digest`.
10. Làm UI: state ở `MusicalizeApp`, `TuningPanel` trong `RoomFrame`, tab `Profile`, local profile.
11. Làm A2 (`dynamics`, `density`).
12. Nghe thủ công 5 variant × 3 preset trước khi chốt.

---

## 15. Ghi chú triển khai

- `render()` nhận BPM từ `FormSpec` hoặc hằng số variant. Không sửa spec global; tính `effective_bpm = int(spec.bpm * tempo + 0.5)` (**int**, half-up) trong `render()` và truyền vào `ctx.bpm` **trước** khi writer chọn pattern. Không nới kiểu `int` ở `model.py`, `guitar.py`, `musicxml.py`.
- `humanize()` chạy sau `render()` và trước `score_to_musicxml`. `piece_seconds()` đọc `score.bpm`, nên BPM hiệu lực phải nằm trên score.
- Dispatch humanize: gọi khi `humanize != 0` hoặc `breath != 0`; bỏ hẳn khi cả hai bằng 0 để legacy `_nh` khớp từng byte. Khi `humanize = 0` mà `breath > 0`, `offsets` vẫn có key với giá trị 0, nên `_clamp_guitar` chỉ được chạy khi `any(offsets.values())`.
- `_TEMPO_CAP` giữ nguyên; `breath` bão hoà khi peak chạm trần — ghi nhận, không giả định tuyến tính.
- `ColorSpec` sinh chuỗi; ở `amount = 1` phải giống từng byte chuỗi hiện tại.
- `sound_for` suy từ `velocity_for`; không scale percent và velocity bằng hai gốc khác nhau.
- `density` chỉ chỉnh fill/bell; không chỉnh giai điệu hay guitar pattern.
- Cache mark là hàm thuần của params đã chuẩn hoá; query chỉ là đầu vào, không phải nhánh logic.
- Default và legacy đúng tổ hợp được pin trong LRU; non-default LRU theo `mtime`.
- Profile name không tham gia hash; đổi tên không mất cache.
- `Default` bất biến ở UI; muốn chỉnh thì “Nhân bản”.
- `dfi_inputs` giữ `digest`; `dfiParamsHash` là field riêng, so ở cả `sessions.py` và `spans.py`; key DFI chỉ thêm hash cho `_p<hash>`.
- DFI corpus median chỉ hiện với Default; profile khác ẩn marker.
- State profile ở `MusicalizeApp`; `TuningPanel` mount một lần trong `RoomFrame`; `Esc` đi qua `useKeyboard` sẵn có.
- `/params/schema` trả `enabled`; client ẩn/disable panel khi server tắt, không chỉ tin biến môi trường.
- Cập nhật `docs/ARCHITECTURE.md` khi thêm `params.py` và ba endpoint; thêm `params.test.ts` vào `test:musicalize`.
- Khi làm AI sau này: AI chỉ sinh JSON `{schema, params}`; server validate; người dùng nghe thử rồi lưu. Không cho AI sinh code hay FFmpeg.
