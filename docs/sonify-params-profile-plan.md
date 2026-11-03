# Parameter profile và bàn tinh chỉnh — Kế hoạch V1

> **Trạng thái**: đã chốt phạm vi, chưa code.
>
> **Liên kết**: [`sonify-humanize-preset-plan.md`](./sonify-humanize-preset-plan.md), [`musicalize-ui-redesign.md`](./musicalize-ui-redesign.md).
>
> **Mục tiêu**: tách các parameter tầng A ra khỏi code, lưu hành vi hiện tại thành `Default`, cho phép tạo profile có tên, và mở một bàn tinh chỉnh ngay trong phòng nghe.

---

## 1. Quyết định đã chốt

| # | Quyết định |
|---|---|
| 1 | V1 chỉ làm **tầng A** — các parameter an toàn, hiệu quả cao. Tầng B (form, harmony, register) và tầng C (thuật toán guitar, trọng số Viterbi) để sau. |
| 2 | Hành vi hiện tại được lưu nguyên vẹn thành **`Default` profile**. Default là mốc so sánh và không được âm thầm đổi tiếng. |
| 3 | Profile có **tên**, tạo được, **đổi tên** được, nhân bản, xoá, reset. |
| 4 | UI mở thành **drawer từ cạnh phải** trên màn rộng và **sheet từ dưới lên** trên điện thoại. Không mở inline để không đẩy chart và không bắt người dùng scroll. Phương án cụ thể ở mục 8. |
| 5 | **Chưa cần auth**. V1 chưa có profile server theo user. |
| 6 | Chưa làm AI tạo profile, chưa làm tầng B/C. Chỉ chỉnh tầng A trước. |

### Đề xuất kỹ thuật đi kèm (chốt khi duyệt)

- `Default` là profile **bất biến**, nằm ở server và được bundle trong app để so khớp.
- Profile người dùng lưu **local** (AsyncStorage). Chia sẻ bằng URL chứa parameter đã chuẩn hoá.
- Built-in preset đơn giản nằm ở server, không cần auth.
- Cache audio dùng **`params_hash`**; Default không đổi tên file để cache cũ vẫn dùng được.
- DFI của bản non-default vẫn được tính và lưu, nhưng **cột so sánh corpus chỉ hiện với Default** trong V1.

---

## 2. Vấn đề

Pipeline hiện tại:

```text
render()  →  humanize()  →  MusicXML  →  MuseScore  →  FFmpeg preset  →  .m4a
```

Parameter nằm rải rác trong code:

| Nhóm | Ví dụ | File |
|---|---|---|
| Form / tempo | `MUSICAL_BARS = 30`, `BPM = 90`, phrase 8 bar, meter 4/4–12/8 | `backend/app/sonify/form.py` |
| Tempo theo dòng | `JAZZ_BPM = 82`, `MINIMALIST_BPM = 118`, `AMBIENT_BPM = 60`, `GUITAR_BPM` 88–120 | `jazz.py`, `minimalist.py`, `ambient.py`, `guitar.py` |
| Dynamics | bảng velocity `p/mp/mf/f`, trần bass `mp`, velocity piano | `dynamics.py` |
| Humanize | trần lệch `±2`, `_TEMPO_DELTA` từng variant, ramp 3 beat, Torroba 3.5%/5%, trần 10%, lilt 4% | `humanize.py` |
| Mix / màu | chuỗi FFmpeg từng variant, noise `0.001` / `0.0003`, gate `0.01` | `preset.py` |
| Render | MuseScore binary, soundfont, số slot export, AAC filter | `audio.py` |

UI hiện tại chỉ có:

- `variant`
- `ensemble`
- `humanize` bật/tắt
- `color` bật/tắt

Các nút này nằm trong `src/musicalize/OptionsPopover.tsx`. URL chỉ mang `h=0/1` và `c=0/1` (`src/musicalize/link.ts`).

### Hệ quả

- Muốn thử một ý tưởng phải sửa Python, tăng `RECAP_REVISION` / `SPAN_REVISION`, deploy, rồi chờ render lại.
- Không có A/B, không có profile, không có URL chia sẻ cấu hình.
- Cache bị xoá hàng loạt mỗi lần đổi một con số.
- Người dùng và AI không có bề mặt nào để tạo biến thể.

---

## 3. Phạm vi V1 — tầng A

### 3.1 Parameter tầng A

Bảy knob dưới đây là bề mặt V1. Tất cả đều là **hệ số nhân hoặc tỉ lệ**, mặc định `1.0`, để một profile dùng được cho mọi variant.

| Key | Nhãn UI | Khoảng | Bước | Default | Ý nghĩa |
|---|---|---:|---:|---:|---|
| `tempo` | Nhịp | `0.75 – 1.25` | `0.01` | `1.00` | Nhân BPM gốc của variant. 1.0 = đúng hiện tại. |
| `humanize` | Người | `0.00 – 2.00` | `0.05` | `1.00` | Nhân trần lệch velocity. 0 = máy hoàn toàn; 1 = hiện tại; 2 = ±4. |
| `breath` | Hơi thở | `0.00 – 1.50` | `0.05` | `1.00` | Nhân độ cong tempo trong câu (nhanh đầu câu, chậm cuối câu). 0 = phẳng. |
| `dynamics` | Tương phản | `0.50 – 1.50` | `0.05` | `1.00` | Nhân độ rộng velocity quanh mốc 64. 1 = bảng p–f hiện tại. |
| `color` | Màu | `0.00 – 1.00` | `0.05` | `1.00` | Lượng wet của preset. 0 = khô hoàn toàn; 1 = chuỗi hiện tại. |
| `noise` | Nhiễu | `0.00 – 1.00` | `0.05` | `1.00` | Nhân nền nhiễu của preset. 0 = không nhiễu. |
| `density` | Mật độ | `0.00 – 1.50` | `0.05` | `1.00` | Nhân độ dài/số lượng fill và bell. 0 = không fill/bell; 1 = hiện tại. |

### 3.2 Cách áp vào code

| Key | Điểm áp | Ghi chú |
|---|---|---|
| `tempo` | `render()` chọn BPM; dùng `replace(spec, bpm=round(spec.bpm * tempo))` | Không sửa `FormSpec` global. `score.bpm` phải là BPM hiệu lực trước `humanize()`. |
| `humanize` | `humanize()`: `CAP = round(2 * humanize)`, `_CHOICES` mở rộng theo CAP | Giữ nguyên `_clamp_guitar`, `_repair`, `_copy_ties`. |
| `breath` | `_tempo_clock()`: nhân `_TEMPO_DELTA`, `_TORROBA_OPEN_DELTA`, `_TORROBA_CLOSE_DELTA`, `_LILT_DELTA` | Giữ trần an toàn `_TEMPO_CAP = 0.10`. `breath = 0` trả `tempos = ()`. |
| `dynamics` | `dynamics.py`: hàm `velocity_for(marking)` và `sound_for(marking)` đọc params | Thay dần các chỗ đang đọc `SOUND[...]`, `PIANO_VELOCITY[...]`, `FILL_VELOCITY` bằng hàm. |
| `color` | `preset.py`: tách chuỗi FFmpeg thành `ColorSpec` có hệ số | Ở `color = 1` phải render ra đúng chuỗi hiện tại. |
| `noise` | `preset.py`: nhân `_SYMPHONY_NOISE` / `_GUITAR_NOISE` | Guitar vẫn giữ gate. |
| `density` | `phrasing.fills()` và `bell_budget()`: nhân `FILL_SPAN`, `BELL_MAX_EIGHTHS` | `density = 0` bỏ fill/bell; `1` giữ nguyên; `>1` kéo dài thêm trong giới hạn an toàn. |

### 3.3 Thứ tự triển khai trong tầng A

Để giảm rủi ro, tầng A chia làm hai đợt:

- **A1 — performance + mix**: `tempo`, `humanize`, `breath`, `color`, `noise`.
- **A2 — texture**: `dynamics`, `density`.

A1 chạm ít module hơn và cho cảm nhận rõ nhất. A2 chạm `dynamics.py` và `phrasing.py`, nên làm sau khi A1 đã ổn định và có test.

### 3.4 Ngoài phạm vi V1

- Form bars/sections/meter.
- Key ring, home key, register bounds.
- Harmony weights, borrowed chords, Viterbi.
- Guitar pattern/profile, ngón tay, dây, giọng.
- AI tạo profile.
- Profile server theo user, auth, quota.
- So sánh DFI xuyên profile.

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
- `schema` là schema version. V1 = `1`.
- **Hash chỉ tính trên `schema + params`**, không tính `id`, `name`, thời gian. Nhờ vậy hai profile khác tên nhưng cùng parameter dùng chung cache audio.

### 4.2 Canonical hash

```text
canonical = json.dumps(
  {"schema": 1, "params": {... thứ tự key cố định ...}},
  separators=(",", ":"),
  sort_keys=True,
)
params_hash = sha256(canonical).hexdigest()[:12]
```

- 12 ký tự hex, đủ để tránh trùng trong thực tế.
- Default hash được pin trong test.
- Server là nơi tính hash chuẩn. Client dùng `paramsKey` (canonical string) cho React key; không cần tự hash.

### 4.3 Preset built-in

V1 có thể có sẵn vài preset để người dùng bắt đầu nhanh. Đây chỉ là các bộ params, không phải code:

| Tên | Ý tưởng | Params gợi ý |
|---|---|---|
| `Default` | Đúng bản đang nghe | tất cả `1.0` |
| `Gần` | Khô, rõ, ít không gian | `color 0.45`, `noise 0.0`, `dynamics 1.1` |
| `Ấm` | Nhiều thân tiếng, chậm hơn một nhịp | `tempo 0.96`, `color 1.0`, `noise 0.8` |
| `Sống` | Nhiều humanize và hơi thở | `humanize 1.4`, `breath 1.2` |
| `Dày` | Nhiều fill/bell hơn | `density 1.25` |

Preset chỉ là điểm bắt đầu; người dùng vẫn sửa và lưu thành profile riêng.

---

## 5. Backend contract

### 5.1 Schema endpoint

`GET /v1/sonify/params/schema`

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
    }
  ],
  "defaultHash": "…"
}
```

- Server là nguồn sự thật về khoảng, default, nhãn, mô tả.
- Client cache schema và có bản fallback bundle để boot offline.

### 5.2 Validate endpoint

`POST /v1/sonify/params/validate`

Request:

```json
{ "schema": 1, "params": { "tempo": 1.4, "humanize": 99 } }
```

Response:

```json
{
  "schema": 1,
  "params": { "tempo": 1.25, "humanize": 2.0, "...": "..." },
  "hash": "…",
  "warnings": [
    "tempo vượt trần, đã kẹp về 1.25",
    "humanize rất cao, có thể làm mất bậc velocity đã viết"
  ]
}
```

Quy tắc:

- Thiếu key → lấy default.
- Key lạ → bỏ qua và cảnh báo (hoặc 400 nếu strict).
- Sai kiểu → 400.
- Số ngoài khoảng → kẹp và cảnh báo.
- Không nhận chuỗi FFmpeg, không nhận code, không nhận key ngoài schema.

### 5.3 Preset endpoint

`GET /v1/sonify/params/presets`

Trả danh sách preset built-in. Không cần auth.

### 5.4 Audio endpoints

Các endpoint hiện tại thêm một query parameter:

```text
p=<base64url(canonical params JSON)>
```

- Default: bỏ trống `p`, hoặc `p` giải mã ra đúng default.
- Legacy `humanize=0` / `color=0` vẫn được nhận và map vào params:
  - `humanize=0` → `params.humanize = 0`
  - `color=0` → `params.color = 0`
- `p` có giới hạn độ dài (khuyến nghị 2048 ký tự) và phải validate trước khi render.
- Nếu `p` sai: trả `400` với thông báo rõ. UI luôn validate trước khi gọi audio.

Các endpoint:

- `GET /v1/stocks/{symbol}/sessions/{date}/recap/audio.m4a`
- `GET /v1/stocks/{symbol}/span/audio.m4a`
- `GET /v1/stocks/{symbol}/session-video.m4a` (nếu có dùng lại pipeline)

`RecapAsset.audio_url` và `movement_audio_path()` phải mang `p` khi profile khác default.

---

## 6. Cache, revision, DFI

### 6.1 Cache key

Hiện tại:

```text
stem = SYMBOL_DATE_VARIANT[-ENSEMBLE]_REVISION_BARCOUNT[_nh][_nc]
```

V1 thêm `params_hash`:

```text
Default:                    …_77_123
Chỉ humanize/color off:     …_77_123_nh
Profile khác default:       …_77_123_p<hash>
```

- Default giữ nguyên tên file → cache cũ vẫn dùng.
- `humanize=0` / `color=0` giữ hậu tố cũ để cache cũ vẫn dùng.
- Mọi thay đổi khác dùng `_p<hash>`.
- Metadata luôn ghi `paramsHash`, `params` (debug), `profileName` (nếu có).

### 6.2 Revision

- `RECAP_REVISION` và `SPAN_REVISION` **không tăng** khi người dùng đổi profile.
- Chỉ tăng khi code hoặc default đổi hành vi.
- `_STORED_NAME` regex thêm nhóm `_p(?P<params>[0-9a-f]{12})`.
- `prune()` phải giữ mọi file có revision hiện tại, bất kể `_p…`, và xoá file cũ theo tuổi.

### 6.3 DFI

- DFI được tính trên score sau humanize, như hiện tại.
- `dfi_inputs` thêm `params_hash`.
- Bản non-default vẫn có DFI score và được lưu.
- **Cột so sánh corpus (signature) chỉ hiện với Default trong V1.** Lý do: DFI của hai profile khác nhau không so sánh được với cùng một median.
- Endpoint `dfi/signatures` nhận `p` (hoặc mặc định default) và lọc theo `params_hash`.
- Khi default đổi hành vi, tăng `DFI_VERSION` nếu công thức đổi; nếu chỉ đổi âm thanh thì không.

---

## 7. Lưu profile

### 7.1 V1 — local profile

Vì chưa có auth:

- `Default` và preset built-in: server.
- Profile người dùng: **AsyncStorage** trên thiết bị.
- Key: `vstock.musicalize.profiles.v1`.
- Cấu trúc:

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
- Tên không rỗng, tối đa 40 ký tự. Khuyến nghị không trùng tên (so sánh không phân biệt hoa thường); nếu trùng, thêm hậu tố.
- Đổi tên chỉ đổi `name`, không đổi `params`, không đổi hash.
- Xoá profile đang dùng → quay về `Default`.
- “Reset” đưa params về default nhưng giữ tên profile.
- Import/export JSON qua clipboard (web và native). V1 chưa cần file picker.

### 7.2 Khi có auth (sau này)

- Chuyển profile lên server, giữ nguyên schema và hash.
- Local profile có thể sync lên.
- Chưa làm trong V1.

---

## 8. UI/UX — phương án phù hợp cá tính app

### 8.1 Cá tính app

Musicalize là một **phòng nghe**, không phải DAW:

- Nền tối, đường kẻ mảnh, chữ nhỏ, đồng hồ mono.
- Điều khiển hiện tại giống mặt máy: shelf thể loại, hàng ensemble, transport tròn.
- Ít nút, ít chữ, ưu tiên nghe.

Vì vậy không nên thêm một sidebar hay một màn “Settings” kiểu ứng dụng văn phòng. Bàn tinh chỉnh nên giống **mở nắp một nhạc cụ**: chỉ hiện khi cần, gọn, có nhãn mono, không chiếm chỗ thường trực.

### 8.2 Đề xuất: drawer bên phải trên màn rộng, sheet từ dưới lên trên điện thoại

Không mở inline. Inline làm dock cao lên, đẩy chart và transport xuống, buộc người dùng scroll — đúng hạn chế bạn vừa nêu. Thay vào đó, bàn tinh chỉnh là một **lớp phủ có chủ đích**, mở ra rồi đóng lại, không làm thay đổi bố cục thường trực.

Cấu trúc hiện tại:

```text
[ Symphony ] [ Jazz ] [ Minimalist ] [ Ambient ] [ Guitar ]
Wood  Brass              DFI  •••(gear)
                          ▶  ↻  🔊  0:00 / 2:00
```

Không thêm hàng mới vào dock — dock wide đang cố định `DOCK_HEIGHT = 232`, thêm hàng sẽ tràn. Thay nút gear hiện tại bằng **nút mở** `Tinh chỉnh · Default` trong `shelfRow` sẵn có:

```text
[ Symphony ] [ Jazz ] [ Minimalist ] [ Ambient ] [ Guitar ]
Wood  Brass          DFI   Tinh chỉnh · Default  ›
                            ▶  ↻  🔊  0:00 / 2:00
```

- `Studio` (quản lý profile) nằm trong tab `Profile` của drawer, không cần nút riêng trên dock.
- Nếu `shelfRow` quá chật trên điện thoại, nút `Tinh chỉnh` được phép wrap xuống một dòng trong dock narrow (dock narrow đã dùng `height: 'auto'`).
- Không tăng `DOCK_HEIGHT`; không đổi chiều cao dock wide.

Hành vi theo kích thước màn hình:

| Màn hình | Cách mở | Vì sao |
|---|---|---|
| `wide` ≥ 960 px (web, tablet ngang) | **Drawer trượt từ cạnh phải**, rộng 360–420 px | Chart vẫn nằm bên trái, không bị đẩy xuống. Ở màn ≥ 1280 px, drawer **push** nhẹ để chart reflow; ở 960–1279 px, drawer **overlay** lên mép phải của chart. |
| `narrow` < 960 px (điện thoại) | **Bottom sheet** trượt từ dưới lên, snap ở 48% và 88% chiều cao | Chart vẫn nhìn thấy ở nửa trên khi sheet ở snap thấp; không cần scroll dock. |

Quy tắc chung:

- **Không có backdrop tối toàn màn hình.** Chỉ một lớp trong suốt để bắt tap ra ngoài; chart vẫn nhìn thấy và vẫn giữ được cảm giác đang nghe.
- Drawer/sheet có **drag handle** ở cạnh hoặc đỉnh; kéo xuống/qua phải để đóng. Trên web, `Esc` đóng.
- Nội dung dài (7 knob + profile) **scroll bên trong drawer/sheet**, không scroll cả trang.
- `TuningPanel` là một component duy nhất; chỉ khác container và hướng animation.
- Nút gear hiện tại được thay bằng nút mở `Tinh chỉnh · Default`; `Studio` nằm ở tab `Profile` bên trong drawer/sheet.
- Transport và chart không bị unmount khi mở drawer; audio tiếp tục phát.

### 8.3 Nội dung drawer/sheet

Hai tab ở đầu, cùng một component:

```text
[ Tinh chỉnh ]  [ Profile ]
```

Tab `Tinh chỉnh`:

Hàng đầu:

```text
Default  • đã sửa        [Lưu] [Hoàn tác]
```

Bốn knob chính, dạng track mảnh, thumb hình thoi nhỏ, giá trị mono bên phải:

```text
Nhịp        ──────◆────  1.00×   (90 BPM)
Người       ───────◆───  1.00
Hơi thở     ──────◆────  1.00
Màu         ────────◆──  1.00
```

Dưới một đường kẻ mảnh, mục “Sâu hơn” (disclosure):

```text
Tương phản  ──────◆────  1.00
Nhiễu       ────────◆──  1.00
Mật độ      ──────◆────  1.00
```

Tab `Profile`:

- Danh sách profile: `Default` (khoá), các profile local.
- Tạo mới, nhân bản, đổi tên, xoá, reset.
- Import/export JSON.
- So sánh A/B: chọn A và B, nghe cùng một đoạn.
- Nút “Dùng profile này” và “Lưu thay đổi”.

Hành vi:

- Kéo slider cập nhật giá trị ngay, nhưng **không tự render audio** mỗi bước.
- Thả tay → nếu “Nghe thử tự động” bật, gọi audio mới; nếu tắt, chờ người dùng bấm “Nghe bản này”.
- Hiển thị BPM suy ra cạnh `Nhịp` (ví dụ `1.00× · 90 BPM`).
- Cảnh báo mềm khi `humanize > 1.5` hoặc `breath > 1.3`, không chặn.
- Haptic nhẹ khi chạm mốc (dùng `expo-haptics` đã có), không rung liên tục khi kéo.
- Nút “Nghe bản này” nằm cố định ở đáy drawer/sheet, không trôi theo scroll.

### 8.4 Kỹ thuật UI đề xuất

- Dùng `Modal` trong suốt + `Animated`/Reanimated cho translateX (drawer) và translateY (sheet). Không cần thêm dependency: `react-native-reanimated` và `react-native-gesture-handler` đã có.
- `wide`: container `position: absolute; right: 0; top: 0; bottom: 0; width: 380`. Nếu dùng push mode, đặt drawer trong một hàng flex với stage và animate width; chỉ bật push ở `width >= 1280`.
- `narrow`: container `position: absolute; left: 0; right: 0; bottom: 0; height: snap`. Snap points tính từ `useWindowDimensions()`, có safe-area inset.
- Không dùng `Modal` full-screen với `animationType="slide"` cho điện thoại vì nó che toàn bộ chart; dùng sheet tự vẽ để giữ chart phía trên.
- Focus: drawer/sheet nhận focus khi mở; `Esc` đóng; tap ra ngoài đóng; không khóa transport keys nếu drawer không cần bàn phím.
- Khi mở drawer, `optionsOpen` vẫn bật để room nhả phím tắt transport, giống `OptionsPopover` hiện tại.

### 8.5 Vì sao không chọn phương án khác

| Phương án | Vì sao không chọn |
|---|---|
| Inline ngay dưới controls | Đẩy chart/transport xuống, buộc scroll, mất ngữ cảnh đang xem chart. |
| Sidebar parameter thường trực | Chiếm chỗ, biến phòng nghe thành DAW, trái cá tính app. |
| Màn Settings riêng | Người dùng phải rời ngữ cảnh đang nghe; chậm thử. |
| Chỉ popover nhỏ như hiện tại | Không đủ chỗ cho 7 knob + profile + A/B. |
| Modal toàn màn hình | Che chart và transport; không còn cảm giác “đang nghe”. |
| Chỉ bottom sheet trên mọi màn | Trên web rộng, drawer bên phải tận dụng chiều ngang tốt hơn và giữ chart gần như nguyên vẹn. |

Phương án drawer phải + sheet dưới giữ được cảm giác “tinh chỉnh tại chỗ”, không phá layout, và không bắt người dùng scroll.

---

## 9. URL và chia sẻ

### 9.1 Format

- Default: giữ URL cũ, không có `p`.
- Profile khác: thêm `p=<base64url(canonical params)>`.
- Legacy `h` / `c` vẫn đọc được.
- `p` chỉ chứa params, không chứa tên profile. Tên là local, không ảnh hưởng âm thanh.

Ví dụ:

```text
?s=VNM&r=1D&g=symphony&p=eyJzY2hlbWEiOjEsInBhcmFtcyI6eyJ0ZW1wbyI6MC45Nn19
```

### 9.2 Round-trip

- `parseLink()` trả `params` đã chuẩn hoá (hoặc `null` = default).
- `writeLink()` ghi `p` khi khác default, bỏ `p` khi default.
- Link cũ `h=0` / `c=0` được map sang params tương ứng.
- Nếu `p` hỏng: fallback về Default, không làm sập phòng nghe.
- Không đưa `paramsHash` vào URL; hash do server tính lại từ `p`.

### 9.3 So sánh A/B

- A = snapshot params đang phát.
- B = params đang chỉnh.
- Chuyển A/B bằng một nút nhỏ cạnh transport.
- Giữ nguyên vị trí phát khi chuyển; nếu audio B chưa render xong, hiện trạng thái “đang dựng”.
- V1.1 nếu thời gian cho phép; không chặn V1.

---

## 10. Validation và an toàn

- Không bao giờ nhận chuỗi FFmpeg từ client.
- Không nhận code, biểu thức, đường dẫn file.
- Chỉ nhận đúng 7 key của schema, đúng kiểu số.
- Kẹp số theo khoảng; cảnh báo thay vì im lặng.
- Giới hạn độ dài `p` và kích thước JSON.
- Rate limit render: dùng cơ chế slot MuseScore hiện có; thêm cảnh báo nếu client tạo quá nhiều profile/params trong thời gian ngắn.
- Cache explosion: `params_hash` tạo nhiều file. Prune theo tuổi như hiện tại; có thể thêm giới hạn số profile active trong V1.1.
- Log `params_hash`, `variant`, `ensemble`, thời gian render để debug.

---

## 11. Test và tiêu chí nghiệm thu

### 11.1 Backend

- `test_params.py`:
  - Default canonical JSON và hash ổn định.
  - Schema đúng default/min/max/step.
  - Normalize: thiếu key → default; số ngoài khoảng → kẹp; key lạ → cảnh báo; sai kiểu → lỗi.
  - Encode/decode `p` round-trip.
  - `tempo = 0.9` đổi BPM và độ dài đúng.
  - `humanize = 0` không còn lệch velocity; `humanize = 2` cho trần ±4.
  - `breath = 0` không sinh tempo event; `breath = 1` khớp hiện tại.
  - `color = 0` dùng WAV khô; `color = 1` khớp chuỗi preset hiện tại.
  - `noise = 0` không trộn nhiễu.
  - `dynamics` co giãn velocity quanh 64.
  - `density = 0` không fill/bell; `density = 1` khớp hiện tại.
- `test_audio_cache.py`:
  - Default giữ nguyên stem.
  - `humanize=0` vẫn dùng `_nh`.
  - Profile khác default sinh `_p<hash>`.
  - Hai profile cùng params nhưng khác tên dùng chung file.
  - Prune giữ file current revision.
- `test_dfi.py`:
  - `params_hash` có trong metadata/DFI inputs.
  - Signature chỉ trả default khi không truyền `p`.
- **Default parity**: render một bộ input cố định với Default, so score/MusicXML với snapshot trước khi tách params.

### 11.2 Frontend

- `params.test.ts`:
  - Default params, encode/decode, legacy `h/c`.
  - Profile CRUD local: tạo, đổi tên, nhân bản, xoá, reset.
  - Tên trùng xử lý đúng.
- `link.test.ts`:
  - `p` round-trip.
  - `p` hỏng fallback Default.
  - Link cũ vẫn hoạt động.
- Kiểm tra UI:
  - Điện thoại: bàn tinh chỉnh là bottom sheet có snap 48%/88%; chart vẫn thấy ở nửa trên; transport không bị đẩy khỏi màn hình.
  - Web rộng: bàn mở drawer từ cạnh phải; chart vẫn thấy và không bị scroll; ở ≥1280 px chart reflow, ở 960–1279 px drawer overlay mép phải.
  - Không có backdrop tối toàn màn hình; tap ra ngoài và `Esc` đóng được.
  - Kéo slider không gọi render liên tục.
  - Đổi profile làm audio URL đổi và không phát nhầm cache.

### 11.3 Tiêu chí nghiệm thu V1

1. `Default` cho ra bản nhạc **y hệt hành vi hiện tại**; test cũ pass; URL/cache cũ vẫn dùng.
2. Chỉnh từng knob tạo ra khác biệt nghe được và không làm hỏng bản nhạc.
3. Tạo profile có tên, đổi tên, nhân bản, xoá, reset; restart app vẫn còn.
4. URL chia sẻ mở lại đúng parameter.
5. Không có cache collision giữa hai profile khác params.
6. DFI của bản non-default không làm bẩn corpus median.
7. UI dùng được trên web và điện thoại, không che transport khi đang nghe.

---

## 12. Phân kỳ công việc

| Phase | Việc | Kết quả |
|---|---|---|
| **0. Nền** | Tạo `params.py`, schema, default, hash, `compose_params`, test default parity | Chưa đổi âm thanh; mọi test cũ pass |
| **1A. Performance + mix** | Nối `tempo`, `humanize`, `breath`, `color`, `noise` vào render/humanize/preset | 5 knob hoạt động qua API |
| **1B. Texture** | Nối `dynamics`, `density` | Đủ 7 knob tầng A |
| **2. Cache + DFI + URL** | `params_hash` vào stem/metadata/prune/DFI; `p` query; legacy map | Không phát nhầm cache; chia sẻ được |
| **3. UI** | `TuningPanel`: drawer phải trên wide, bottom sheet trên narrow; tab `Profile`, profile local, A/B nếu kịp | Người dùng tự chỉnh và lưu, không mất chart |
| **4. Sau V1** | Tầng B/C, profile server, auth, AI sinh JSON | Để sau |

Thứ tự ưu tiên nếu thời gian hẹp:

1. Phase 0 + 1A + 2 (backend đúng và chia sẻ được).
2. Phase 3 bản tối giản: nút “Tinh chỉnh” + drawer/sheet + lưu profile.
3. 1B.
4. Tab `Profile` đầy đủ + A/B.

---

## 13. Rủi ro và cách giảm

| Rủi ro | Cách giảm |
|---|---|
| Default bị lệch tiếng | Snapshot score/MusicXML trước khi tách; test parity; không tăng revision nếu không cần. |
| `dynamics`/`density` chạm nhiều module | Để A2; thay dần hằng số bằng hàm; test từng module. |
| ContextVar rò rỉ giữa request | Dùng `compose_params` context manager, reset trong `finally`; `asyncio.to_thread` đã copy context. |
| Global `FormSpec` bị sửa | Luôn `replace(spec, bpm=...)`; không mutate `DAILY_SPEC`. |
| Cache phình | Prune theo tuổi; giới hạn profile active; hash 12 ký tự. |
| DFI lẫn profile | Lưu `params_hash`; signature chỉ default trong V1. |
| UI quá giống DAW | Track mảnh, nhãn mono, không sidebar; chỉ mở khi cần. |
| Drawer/sheet che chart | Không backdrop tối; wide dùng drawer phải và push ở ≥1280 px; narrow dùng sheet snap 48% để chart vẫn thấy. |
| Slider gọi render liên tục | Chỉ render khi thả tay hoặc bấm “Nghe bản này”; debounce. |
| Tên profile trùng | Chuẩn hoá tên, cảnh báo, thêm hậu tố. |

---

## 14. Việc cần làm ngay khi bắt tay

1. Tạo `backend/app/sonify/params.py` với `DEFAULT_PARAMS`, `PARAM_SCHEMA`, `normalize_params`, `profile_hash`, `compose_params`.
2. Viết test default parity trên một input cố định (score + MusicXML).
3. Nối `tempo` và `humanize` trước — hai knob ít chạm module nhất.
4. Nối `breath` và `color`/`noise`.
5. Làm `p` query + cache hash + legacy map.
6. Làm UI `TuningPanel` (drawer phải trên wide, bottom sheet trên narrow) + tab `Profile` + local profile.
7. Làm A2 (`dynamics`, `density`).
8. Nghe thủ công 5 variant × 3 preset trước khi chốt.

---

## 15. Ghi chú triển khai

- `render()` hiện nhận `bpm` từ `FormSpec` hoặc hằng số variant. Không sửa các spec global; tính BPM hiệu lực trong `render()`.
- `humanize()` chạy sau `render()` và trước `score_to_musicxml`. `tempo` phải có hiệu lực trước `humanize()` để tempo clock đúng.
- `piece_seconds()` đọc `score.bpm` và `score.bar_beats`; vì vậy BPM hiệu lực phải nằm trên score.
- `color` phải refactor `preset.py` từ chuỗi FFmpeg hardcode sang `ColorSpec` có hệ số, nhưng ở `amount = 1` phải render ra đúng chuỗi hiện tại. Test khóa chuỗi default.
- `noise` chỉ có tác dụng với `symphony` và `guitar`; các variant khác bỏ qua như hiện tại.
- `dynamics` nên đi qua hàm `velocity_for()` / `sound_for()` thay vì đọc dict toàn cục, để `compose_params` có hiệu lực ở mọi chỗ.
- `density` chỉ chỉnh fill/bell trong V1; không chỉnh số nốt giai điệu, không chỉnh guitar pattern.
- UI không mở inline: wide dùng drawer phải (overlay 960–1279 px, push ≥1280 px), narrow dùng bottom sheet snap 48%/88%. Chart và transport không bị đẩy xuống, không cần scroll.
- Profile name không tham gia hash. Đổi tên không được làm mất cache.
- `Default` phải là bất biến ở UI; muốn chỉnh thì “Nhân bản”.
- DFI corpus median chỉ hiện với Default trong V1. Nếu UI đang hiện score của profile khác, ẩn dấu median hoặc ghi “chỉ so sánh trong Default”.
- Khi mở gate cho người dùng, chỉ cần expose schema/preset/validate; không cần đổi pipeline.
- Khi làm AI sau này: AI chỉ sinh JSON `{schema, params}`; server validate; người dùng nghe thử rồi lưu. Không cho AI sinh code hay FFmpeg.
