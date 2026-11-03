# Parameter profile và bàn tinh chỉnh — Kế hoạch V1

> **Trạng thái**: đã đối chiếu code, chưa code.
>
> **Liên kết**: [`sonify-humanize-preset-plan.md`](./sonify-humanize-preset-plan.md), [`musicalize-ui-redesign.md`](./musicalize-ui-redesign.md).
>
> **Mục tiêu**: tách các parameter tầng A ra khỏi code, lưu hành vi hiện tại thành `Default`, cho phép tạo profile có tên, và mở một bàn tinh chỉnh ngay trong phòng nghe.

---

## 0. Sửa sau vòng đối chiếu code

Bốn lỗi chặn đã được xử lý trong bản này:

| # | Vấn đề | Cách sửa trong doc |
|---|---|---|
| 1 | `tempo` không phải phép nhân thuần trên guitar: `BARRIOS_TREMOLO_MIN_BPM = 90` quyết định **có viết tremolo hay không**, và writer đọc `ctx.bpm`. | Chốt: BPM hiệu lực được đặt **trước khi writer chạy**; dưới 90 thì tremolo tự rơi. Không clamp. Ghi rõ hệ quả và test. §3.2, §3.3 |
| 2 | `humanize` nhân nhầm `CAP` hai vai trò (trần offset và ngưỡng freeze), cộng banker's rounding làm 5 bước slider không đổi gì. | Tách `FREEZE_GAP = 2` cố định khỏi `offset_cap = 2 × humanize` dạng float; làm tròn có kiểm soát để 0.05 bước vẫn đổi. §3.4 |
| 3 | `prune()` xoá mọi file không khớp `_STORED_NAME`, chạy mỗi lần `get()`. | Nâng thành blocker Phase 0: sửa regex + test “render profile mới xong không bị xoá”. §6.2 |
| 4 | DFI recompose ngoài đường audio dùng key không có `params_hash`, nên DFI profile khác ghi đè DFI Default. | Thread hash vào `_recap_key`, `_movement_key`, `dfi_inputs` và `/dfi/pieces`. §6.4 |

Các điểm “nên sửa” còn lại (dynamics, color, schema, LRU, `p` ở peaks, UI overflow, a11y, kill switch) đã vào §3.5–§3.7, §5, §6.3, §6.5, §8, §10, §12.

---

## 1. Quyết định đã chốt

| # | Quyết định |
|---|---|
| 1 | V1 chỉ làm **tầng A** — parameter an toàn, hiệu quả cao. Tầng B (form, harmony, register) và tầng C (thuật toán guitar, trọng số Viterbi) để sau. |
| 2 | Hành vi hiện tại được lưu nguyên vẹn thành **`Default` profile**. Default là mốc so sánh và không được âm thầm đổi tiếng. |
| 3 | Profile có **tên**, tạo được, **đổi tên** được, nhân bản, xoá, reset. |
| 4 | UI mở thành **drawer từ cạnh phải** trên màn rộng và **sheet từ dưới lên** trên điện thoại. Không mở inline để không đẩy chart và không bắt người dùng scroll. Chi tiết ở §8. |
| 5 | **Chưa cần auth**. V1 chưa có profile server theo user. |
| 6 | Chưa làm AI tạo profile, chưa làm tầng B/C. Chỉ chỉnh tầng A trước. |
| 7 | `tempo` thấp làm rơi tremolo guitar là **hành vi được chấp nhận**, không clamp BPM. Writer dùng BPM hiệu lực, nên chọn pattern và score luôn nhất quán. |
| 8 | `humanize` là knob **liên tục 0–1.5, step 0.05**. Trần offset tách khỏi ngưỡng freeze. Không mở lại vùng ±4 đã bị loại trong `sonify-humanize-preset-plan.md`. |
| 9 | Cache non-default dùng **LRU theo `params_hash`**, không giữ tất cả 30 ngày. Default và legacy `_nh/_nc` được pin. |

### Đề xuất kỹ thuật đi kèm

- `Default` là profile **bất biến**, nằm ở server và được bundle trong app để so khớp.
- Profile người dùng lưu **local** (AsyncStorage). Chia sẻ bằng URL chứa parameter đã chuẩn hoá.
- Built-in preset đơn giản nằm ở server, không cần auth.
- Cache audio dùng **`params_hash`**; Default không đổi tên file để cache cũ vẫn dùng được.
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
| Mix / màu | chuỗi FFmpeg từng variant, noise `0.001` / `0.0003`, gate `0.01` | `preset.py` |
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

Tất cả là **hệ số**, mặc định `1.0`, để một profile dùng được cho mọi variant.

| Key | Nhãn UI | Khoảng | Bước | Default | Ý nghĩa |
|---|---|---:|---:|---:|---|
| `tempo` | Nhịp | `0.75 – 1.25` | `0.01` | `1.00` | Nhân BPM gốc của variant. 1.0 = đúng hiện tại. |
| `humanize` | Người | `0.00 – 1.50` | `0.05` | `1.00` | Nhân trần lệch velocity. 0 = máy hoàn toàn; 1 = hiện tại; 1.5 = ±3. |
| `breath` | Hơi thở | `0.00 – 1.50` | `0.05` | `1.00` | Nhân độ cong tempo trong câu. 0 = phẳng; 1 = hiện tại. |
| `dynamics` | Tương phản | `0.50 – 1.50` | `0.05` | `1.00` | Co giãn velocity quanh mốc 64. 1 = bảng p–f hiện tại. |
| `color` | Màu | `0.00 – 1.00` | `0.05` | `1.00` | Lượng wet của preset. 0 = khô; 1 = chuỗi hiện tại. |
| `noise` | Nhiễu | `0.00 – 1.00` | `0.05` | `1.00` | Nhân nền nhiễu của preset. 0 = không nhiễu. |
| `density` | Mật độ | `0.00 – 1.50` | `0.05` | `1.00` | Nhân độ dài/số lượng fill và bell. 0 = không fill/bell; 1 = hiện tại. |

### 3.2 `tempo` — BPM hiệu lực, không phải phép nhân hậu kỳ

`tempo` **không** được áp sau khi score đã viết. Nó phải có hiệu lực trước khi writer guitar đọc `ctx.bpm` và trước `humanize()`:

1. Chọn `spec` của variant như hiện tại.
2. `effective_bpm = round(spec.bpm * tempo, 2)`.
3. Truyền `effective_bpm` vào `render()` và vào `ctx.bpm`; không mutate `DAILY_SPEC` hay spec global.
4. `score.bpm = effective_bpm` trước `humanize()` và trước `piece_seconds()`.

Hệ quả đã chốt: các ngưỡng guitar dùng **BPM hiệu lực**, nên hạ tempo có thể làm rơi tremolo/sixteenths:

| Ensemble | BPM gốc | `tempo` làm rơi ngưỡng 90 |
|---|---:|---|
| `torroba` | 96 | `≤ 0.93` (90/96) |
| `villa` | 100 | `< 0.90` (90/100) |
| `bach` | 96 | `≤ 0.93` |
| `brouwer` | 108 | `≤ 0.83` (90/108) |
| `sor` | 88 | đã dưới 90 ở Default |

Đây là **hành vi đúng**, không phải lỗi: nếu bản chậm đến mức không còn tremolo thì viết tremolo sẽ sai nhạc. UI hiện BPM suy ra và, với guitar, ghi chú “dưới ngưỡng tremolo” khi BPM hiệu lực < 90. Test bắt buộc: `torroba` ở `tempo = 0.9` cho 86.4 BPM, không có tremolo, và score ghi đúng BPM đó.

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
- `offset_cap = 2.0 * humanize` dạng **float**.
- `chosen_offset` vẫn dùng FNV trên `(variant, ensemble, field, bar, tick)` để ổn định giữa process:
  - `base = _CHOICES[value % 5]` như hiện tại;
  - `target = base * humanize`;
  - `offset = sign(target) * round_magnitude(|target|)`, với phần lẻ quyết định bằng một bit hash thứ hai, để 0.05 bước thay đổi phân bố chứ không bị dồn về cùng một số nguyên.
- Ở `humanize = 1`, `target` là số nguyên → offset **trùng tuyệt đối** hiện tại, đảm bảo Default parity.
- `humanize = 0` → offset 0 toàn bộ.
- `humanize = 1.5` → trần ±3, nằm trong vùng đã kiểm chứng; không mở lại ±4.

Range dừng ở `1.5`, step `0.05`, cảnh báo mềm khi `> 1.25`.

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

`amount` (0–1) biến đổi:

- gain dB nhân `amount`;
- decay nhân `amount`;
- `softclip_threshold` lerp về `1.0` (bypass) khi `amount → 0`;
- delay giữ nguyên, chỉ bỏ tap khi decay = 0;
- `amount = 0` bỏ hẳn filter màu, dùng WAV khô.

Chuỗi FFmpeg được **sinh** từ spec theo thứ tự cố định. Ở `amount = 1`, chuỗi phải **giống từng byte** chuỗi hiện tại; test khoá chuỗi Default cho cả 5 variant. Mọi giá trị khác là kết quả của spec, không phải “mò hệ số”.

### 3.7 `density` và `noise`

- `density` nhân `FILL_SPAN`, `FILL_MIN`, `BELL_MAX_EIGHTHS` trong `phrasing.py`; `0` bỏ fill/bell, `1` giữ nguyên, `>1` kéo dài trong giới hạn an toàn. Không chỉnh số nốt giai điệu, không chỉnh guitar pattern.
- `noise` nhân `_SYMPHONY_NOISE` / `_GUITAR_NOISE`; guitar vẫn giữ gate `0.01`; variant khác bỏ qua như hiện tại.

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
  "schema": 1,
  "id": "default",
  "name": "Default",
  "params": {
    "tempo": 1.0,
    "humanize": 1.0,
    "breath": 1.0,
    "dynamics": 1.0,
    "color": 1.0,
    "noise": 1.0,
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
  {"schema": 1, "params": params},
  separators=(",", ":"),
  sort_keys=True,
)
params_hash = sha256(canonical).hexdigest()[:12]
```

- **Round theo step trước khi hash.** Nếu không, `0.9600000000000001` tạo hash khác `0.96` dù nghe giống hệt.
- `round(..., 2)` để xoá bụi float sau khi nhân step.
- Server là nơi tính hash chuẩn. Client dùng `paramsKey` (canonical string) cho React key; không tự hash.
- Default hash được pin trong test. Với canonical ở §4.1: `35d9a160e9a3`.

### 4.3 Preset built-in

| Tên | Ý tưởng | Params gợi ý |
|---|---|---|
| `Default` | Đúng bản đang nghe | tất cả `1.0` |
| `Gần` | Khô, rõ, ít không gian | `color 0.45`, `noise 0.0`, `dynamics 1.1` |
| `Ấm` | Nhiều thân tiếng, chậm hơn một nhịp | `tempo 0.96`, `color 1.0`, `noise 0.8` |
| `Sống` | Nhiều humanize và hơi thở | `humanize 1.25`, `breath 1.2` |
| `Dày` | Nhiều fill/bell hơn | `density 1.25` |

Preset chỉ là điểm bắt đầu; người dùng vẫn sửa và lưu thành profile riêng.

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
  "schema": 1,
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
  "defaultHash": "35d9a160e9a3"
}
```

Hai nhóm khớp disclosure “Sâu hơn” ở UI; nhóm `performance` chứa `tempo`, `humanize`, `breath`, `color`. Các field nhóm `texture` ở ví dụ trên lược bớt `min/max/step/default` cho gọn; schema thật có đủ, sinh từ `params.py`.

### 5.2 Validate

`POST /v1/sonify/params/validate`

Request:

```json
{ "schema": 1, "params": { "tempo": 1.4, "humanize": 99 } }
```

Response:

```json
{
  "schema": 1,
  "params": { "tempo": 1.25, "humanize": 1.5, "breath": 1.0, "dynamics": 1.0, "color": 1.0, "noise": 1.0, "density": 1.0 },
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
- Cảnh báo mềm `high_humanize`, `high_breath`, `tremolo_below_min` (khi variant guitar và BPM hiệu lực < 90).
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
  - `humanize=0` → `params.humanize = 0`
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
{"params":{"breath":1.0,"color":1.0,"density":1.0,"dynamics":1.0,"humanize":1.0,"noise":1.0,"tempo":0.96},"schema":1}
```

```text
p=eyJwYXJhbXMiOnsiYnJlYXRoIjoxLjAsImNvbG9yIjoxLjAsImRlbnNpdHkiOjEuMCwiZHluYW1pY3MiOjEuMCwiaHVtYW5pemUiOjEuMCwibm9pc2UiOjEuMCwidGVtcG8iOjAuOTZ9LCJzY2hlbWEiOjF9
```

---

## 6. Cache, revision, DFI

### 6.1 Cache mark là hàm thuần của params

Không để query quyết định tên file. Normalize trước, rồi mới chọn mark:

```python
def cache_mark(params) -> str:
    canonical = normalize_params(params)
    if canonical == DEFAULT_PARAMS:
        return ""                       # cache cũ, không đổi tên
    if only_legacy_layers_off(canonical):
        return legacy_layer_mark(canonical)   # "_nh", "_nc", "_nh_nc"
    return f"_p{params_hash(canonical)}"
```

Nhờ vậy:

- `h=0` và `p` có `humanize: 0` cho **cùng một** tên file `_nh`, không sinh hai bản.
- `h=0&c=0` cho `_nh_nc`, đúng cache cũ.
- Mọi tổ hợp khác cho `_p<hash>`.

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

### 6.4 DFI — cả đường audio lẫn đường recompose

DFI hiện được compose lại ngoài audio qua `dfi_service.recap_dfi(...)` (`services/sessions.py:246`). Key cache `_recap_key` / `_movement_key` (`services/dfi.py:145-175`) chỉ có `RC_REV + DFI_VERSION + digest + variant + ensemble + humanize + color`. Thiếu `params_hash` thì DFI của profile khác **ghi đè** DFI Default cùng piece.

Phải sửa cả bốn chỗ:

1. `_recap_key` và `_movement_key` thêm `params_hash`.
2. `dfi_inputs` lưu `f"{digest}:{params_hash}"` (hoặc thêm field `dfiParamsHash`) và `sessions.py` so cả hai, không chỉ `digest`.
3. `/v1/sonify/dfi/pieces` nhận `p` và compose theo params, không dùng cache Default.
4. Metadata DFI ghi `paramsHash` để debug.

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
  "schema": 1,
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
- “Reset” đưa params về default nhưng giữ tên profile.
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
- `TuningPanel` được mount **một lần trong `RoomFrame`**, không mount riêng ở `LiveRoom` và `ReplayRoom`. Hai room truyền `tuning` node + state xuống; trigger nằm trong `Controls`.
- `Esc` đi qua `useKeyboard` sẵn có của `ReplayRoom`: thêm `tuningOpen` vào điều kiện `!paletteOpen && !optionsOpen`, không đăng ký listener thứ hai.

### 8.3 Nội dung drawer/sheet

Hai tab:

```text
[ Tinh chỉnh ]  [ Profile ]
```

Tab `Tinh chỉnh`:

```text
Default  • đã sửa        [Lưu] [Hoàn tác]

Nhịp        ──────◆────  1.00×   (90 BPM)
Người       ───────◆───  1.00
Hơi thở     ──────◆────  1.00
Màu         ────────◆──  1.00

── Sâu hơn ─────────────────
Tương phản  ──────◆────  1.00
Nhiễu       ────────◆──  1.00
Mật độ      ──────◆────  1.00
```

Tab `Profile`:

- Danh sách profile: `Default` (khoá), các profile local.
- Tạo mới, nhân bản, đổi tên, xoá, reset.
- Import/export JSON.
- Nút “Dùng profile này” và “Lưu thay đổi”.
- Không có A/B trong V1; nếu làm, ghi rõ `(V1.1)` và không đưa vào AC V1.

Hành vi:

- Kéo slider cập nhật giá trị ngay, **không render audio mỗi bước**.
- Thả tay → nếu “Nghe thử tự động” bật thì gọi audio mới; nếu tắt, chờ “Nghe bản này”.
- Hiển thị BPM suy ra cạnh `Nhịp` (ví dụ `1.00× · 90 BPM`); guitar dưới 90 BPM hiện ghi chú “dưới ngưỡng tremolo”.
- Cảnh báo mềm `humanize > 1.25`, `breath > 1.2`, không chặn.
- Haptic nhẹ khi chạm mốc (`expo-haptics` đã có), không rung liên tục khi kéo.
- Nút “Nghe bản này” cố định ở đáy drawer/sheet.

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
- `writeLink()` ghi `p` khi khác default, bỏ `p` khi default.
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
- **Kill switch**: `VSTOCK_SONIFY_PARAMS=0` buộc server bỏ qua `p` và dùng Default; `EXPO_PUBLIC_SONIFY_PARAMS=0` ẩn nút `Tinh chỉnh` trên client. Dùng để xác nhận Default parity trên production trước khi mở.
- Rollout: bật server trước (chấp nhận `p`), đo parity; sau đó bật client.

---

## 11. Test và tiêu chí nghiệm thu

### 11.1 Backend

`test_params.py`:

- Default canonical JSON và hash `35d9a160e9a3` ổn định.
- Round theo step trước khi hash: `0.9600000000000001` và `0.96` cùng hash.
- Schema đúng default/min/max/step, đủ hai nhóm.
- Normalize: thiếu key → default; ngoài khoảng → kẹp; key lạ → `unknown_key`; sai kiểu → lỗi.
- Encode/decode `p` round-trip.

`test_tempo.py`:

- `tempo = 1` khớp BPM gốc từng variant.
- `tempo = 0.9` đổi BPM và độ dài đúng.
- `torroba` ở `0.9` = 86.4 BPM → **không tremolo**, score ghi 86.4.
- Writer nhận `ctx.bpm` hiệu lực, không phải BPM danh nghĩa.

`test_humanize.py`:

- `humanize = 1` khớp tuyệt đối offset hiện tại.
- `humanize = 0` không offset.
- `humanize = 1.05` khác `1.0` (không bị banker's rounding chặn).
- `FREEZE_GAP` không đổi khi humanize đổi.
- `breath = 0` không tempo event; `breath = 1` khớp hiện tại.
- `breath = 1.5` lệch nhiều hơn `1.0` trên variant còn dư trần; Torroba ghi nhận bão hoà.

`test_color.py`:

- `amount = 1` sinh đúng từng byte chuỗi Default cho cả 5 variant.
- `amount = 0` không filter màu.
- `amount = 0.5` giảm gain/decay theo spec, threshold lerp đúng.

`test_dynamics.py`:

- `dynamics = 1` khớp bảng hiện tại.
- `sound_for` suy từ `velocity_for` (`round(vel/90*100)`).
- Không module nào ngoài `dynamics.py` import trực tiếp `SOUND` / `PIANO_VELOCITY`.
- Ghép `dynamics 1.5 × humanize 1.5` không làm vỡ freeze/repair.

`test_audio_cache.py`:

- Default giữ nguyên stem.
- `h=0` và `p{humanize:0}` cho **cùng** tên `_nh`.
- Profile khác default sinh `_p<hash>`.
- Hai profile cùng params khác tên dùng chung file.
- **Prune giữ file `_p…` vừa ghi**; file revision cũ bị xoá.
- LRU giữ đúng `VSTOCK_PARAMS_CACHE_MAX` hash, xoá mtime cũ nhất, không đụng Default/legacy.

`test_dfi.py`:

- `params_hash` có trong `_recap_key`, `_movement_key`, `dfi_inputs`, metadata.
- Hai profile khác params không ghi đè DFI của nhau.
- `/dfi/pieces` với `p` trả DFI của đúng params.
- Signature không nhận `p`; UI ẩn marker khi params ≠ default.

**Default parity**: render một bộ input cố định với Default, so score + MusicXML với snapshot trước khi tách params.

### 11.2 Frontend

`params.test.ts` (phải thêm vào script `test:musicalize` trong `package.json:51`):

- Default params, encode/decode, legacy `h/c`.
- Round theo step trước khi encode.
- Profile CRUD local: tạo, đổi tên, nhân bản, xoá, reset; tên trùng.
- `cacheMark` phía client (nếu có) khớp server.

`link.test.ts`:

- `p` round-trip.
- `p` hỏng/quá dài fallback Default.
- Link cũ vẫn hoạt động.
- `p` xuất hiện ở audio URL **và** peaks URL.

UI:

- Điện thoại: bottom sheet snap 48%/88%; chart thấy ở nửa trên; transport không bị đẩy khỏi màn hình.
- Web 960 px và 1280 px: nút `Tinh chỉnh · Default` không tràn, tên dài ellipsis; drawer overlay/push đúng ngưỡng.
- Không backdrop tối; tap ngoài và `Esc` đóng.
- Kéo slider không gọi render liên tục.
- Đổi profile làm audio URL và peaks URL đổi cùng nhau, không phát nhầm cache.
- Slider có role `adjustable`, arrow keys hoạt động.

### 11.3 Tiêu chí nghiệm thu

**Backend (V1 bắt buộc)**

1. Default cho ra score/MusicXML **y hệt** trước khi tách params; test cũ pass; cache cũ vẫn dùng.
2. Bảy knob có hiệu lực qua `p`; `tempo` áp trước writer; tremolo rơi đúng ngưỡng.
3. Không có cache collision; `prune()` không xoá bản non-default; LRU bounded.
4. DFI của profile khác không ghi đè DFI Default.
5. `p` round-trip; legacy `h/c` vẫn chạy.

**V1 UI (bắt buộc)**

6. Tạo profile có tên, đổi tên, nhân bản, xoá, reset; restart app vẫn còn.
7. URL chia sẻ mở lại đúng parameter.
8. Drawer/sheet dùng được trên web và điện thoại, không che transport, không bắt scroll chart.

**V1.1 (không chặn)**

9. A/B nghe song song.
10. Quản lý profile nâng cao, import/export hàng loạt.

---

## 12. Phân kỳ công việc

| Phase | Việc | Kết quả |
|---|---|---|
| **0. Nền + an toàn cache** | `params.py`, schema generated, default hash, `compose_params`, `cache_mark`, sửa `_STORED_NAME`, test prune + parity | Chưa đổi âm thanh; không mất file |
| **1A. Performance + mix** | Nối `tempo` (trước writer), `humanize` (tách freeze), `breath`, `ColorSpec`, `noise` | 5 knob hoạt động qua API |
| **1B. Texture** | Nối `dynamics` (hàm suy ra), `density` | Đủ 7 knob |
| **2. Cache + DFI + URL** | LRU, DFI keys, `p` cho audio/peaks/dfi, legacy map | Không phát nhầm cache; chia sẻ được |
| **3. UI** | `TuningPanel` mount trong `RoomFrame`, drawer/sheet, tab `Profile`, local profile, a11y | Người dùng tự chỉnh và lưu |
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
| `humanize` đổi cấu trúc freeze | Tách `FREEZE_GAP` khỏi `offset_cap`; test 1.0 parity và 1.05 khác 1.0. |
| `prune()` xoá audio mới | Sửa regex Phase 0; test prune trước khi render profile đầu tiên. |
| DFI profile ghi đè Default | Thread hash vào `_recap_key`, `_movement_key`, `dfi_inputs`, `/dfi/pieces`. |
| `dynamics`/`density` chạm nhiều module | A2; thay dict bằng hàm; test cấm import dict; test ghép humanize. |
| ContextVar rò rỉ giữa request | `compose_params` context manager, reset trong `finally`; `asyncio.to_thread` copy context. |
| Global `FormSpec` bị sửa | Luôn `replace(spec, bpm=...)`. |
| Cache phình | LRU theo hash; pin Default/legacy; hash 12 ký tự. |
| `p` chỉ đổi audio, không đổi peaks | `paramsQuery` dùng chung cho audio, peaks, movement, dfi pieces. |
| Nút mở tràn ở 960 px | `maxWidth`, `flexShrink`, ellipsis; test 960 và 1280. |
| UI quá giống DAW | Track mảnh, nhãn mono, không sidebar; chỉ mở khi cần. |
| Slider render liên tục | Chỉ render khi thả tay hoặc bấm “Nghe bản này”; debounce. |
| Tên profile trùng | Chuẩn hoá, cảnh báo, thêm hậu tố. |

---

## 14. Việc cần làm ngay khi bắt tay

1. Tạo `params.py` với `DEFAULT_PARAMS`, `PARAM_SCHEMA`, `normalize_params`, `params_hash`, `cache_mark`, `compose_params`.
2. Sửa `_STORED_NAME` + test `prune()` giữ `_p…` **trước** khi render bất kỳ profile nào.
3. Viết test default parity trên input cố định (score + MusicXML).
4. Sinh schema generated + CI diff.
5. Nối `tempo` (trước writer, có test tremolo) và `humanize` (tách freeze).
6. Nối `breath` và `ColorSpec`/`noise`.
7. Làm `p` + cache hash + legacy map cho audio **và** peaks.
8. Thread hash vào DFI recompose.
9. Làm UI `TuningPanel` trong `RoomFrame` + tab `Profile` + local profile.
10. Làm A2 (`dynamics`, `density`).
11. Nghe thủ công 5 variant × 3 preset trước khi chốt.

---

## 15. Ghi chú triển khai

- `render()` nhận BPM từ `FormSpec` hoặc hằng số variant. Không sửa spec global; tính BPM hiệu lực trong `render()` và truyền vào `ctx.bpm` **trước** khi writer chọn pattern.
- `humanize()` chạy sau `render()` và trước `score_to_musicxml`. `piece_seconds()` đọc `score.bpm`, nên BPM hiệu lực phải nằm trên score.
- `_TEMPO_CAP` giữ nguyên; `breath` bão hoà khi peak chạm trần — ghi nhận, không giả định tuyến tính.
- `ColorSpec` sinh chuỗi; ở `amount = 1` phải giống từng byte chuỗi hiện tại.
- `sound_for` suy từ `velocity_for`; không scale percent và velocity bằng hai gốc khác nhau.
- `density` chỉ chỉnh fill/bell; không chỉnh giai điệu hay guitar pattern.
- Cache mark là hàm thuần của params đã chuẩn hoá; query chỉ là đầu vào, không phải nhánh logic.
- Default pin trong LRU; non-default LRU theo `mtime`.
- Profile name không tham gia hash; đổi tên không mất cache.
- `Default` bất biến ở UI; muốn chỉnh thì “Nhân bản”.
- DFI corpus median chỉ hiện với Default; profile khác ẩn marker.
- `TuningPanel` mount một lần trong `RoomFrame`; `Esc` đi qua `useKeyboard` sẵn có.
- Cập nhật `docs/ARCHITECTURE.md` khi thêm `params.py` và ba endpoint; thêm `params.test.ts` vào `test:musicalize`.
- Khi làm AI sau này: AI chỉ sinh JSON `{schema, params}`; server validate; người dùng nghe thử rồi lưu. Không cho AI sinh code hay FFmpeg.
