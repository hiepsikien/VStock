# Volume ba bè guitar — Kế hoạch

> **Trạng thái**: đã vào code.
>
> **Đọc cùng**: [`sonify-params-profile-plan.md`](./sonify-params-profile-plan.md), [`musicalize-plan.md`](./musicalize-plan.md), [`sonify-instrument-sets.md`](./sonify-instrument-sets.md).
>
> **Mục tiêu**: thêm ba knob cân bằng bè **cao / trung / bass** cho variant `guitar` trong bàn tinh chỉnh, giữ `Default` bất biến, và không đổi kiến trúc render hiện tại.

---

## 1. Kết luận

Làm được với pipeline hiện tại, nhưng phải hiểu đúng bản chất:

- Pipeline guitar xuất **một file mix duy nhất** từ **một part nylon**. Không có stem, nên không thể vặn volume từng bè sau khi render.
- Ba bè đã tách sẵn trong `Score` (`lead`, `support`, `low`), và âm thanh guitar đang dựa vào **velocity từng nốt** để cân bằng. Vì vậy thêm ba độ lệch velocity là đủ.
- Đây là **cân bằng velocity**, không phải gain thuần. Nó đổi cả lớp sample/timbre khi đi xa khỏi 0.
- Nếu cần fader thật, mute sạch, hoặc kéo volume khi đang phát, phải tách part/stem — việc lớn hơn, xem §6.

---

## 2. Hiện trạng

### 2.1 Ba bè đã tách trong `Score`

`backend/app/sonify/model.py:223-227` giữ năm field; guitar dùng ba:

| Bè người nghe | Field trong `Score` | Voice trong MusicXML | Ghi chú |
|---|---|---|---|
| Cao | `lead` | 1 | Đường giá / giai điệu |
| Trung | `support` | 2 và 4 | Preludio tách hai voice giữa |
| Bass | `low` | 3 | Ngón cái, root, đôi khi mang giai điệu |

`backend/app/sonify/guitar.py:285-289` — guitar gán `lead` vào voice 1, `support` vào 2/4, `low` vào voice 3; `guitar.py:298` đặt `variant="guitar"`.
`backend/app/sonify/musicxml.py:1205-1223` — `_guitar_voices()` xếp đúng thứ tự **lead → từng voice support → low**; `_guitar_part()`: “One nylon part. The lead, each support voice, and the bass share the measure.”

Vì vậy ba bè không cần tách mới ở tầng dữ liệu; chúng đã là ba nhóm luồng độc lập trước khi vào MuseScore (`support` có thể là hai voice nhưng vẫn chung một knob).

### 2.2 Velocity từng nốt đang là cơ chế cân bằng thật

- `backend/app/sonify/guitar.py:53-56` — các mức cố định: `_MELODY = 64`, `_INNER = 56`, `_BASS = 60`.
- `backend/app/sonify/guitar.py:79` — `TREMOLO_BASS_TRIM = 2` hạ thumb tremolo.
- `backend/app/sonify/audio.py:873-891` — guitar cố ý **không dùng MuseSounds nylon**, vì sampler đó bỏ qua velocity từng nốt; part giữ **MS Basic** để velocity “speaks”.
- `backend/tests/test_recap.py:514-534` — `test_nylon_guitar_stays_on_ms_basic_so_note_velocities_speak` khoá hành vi **chọn sound**, chưa chứng minh MuseScore áp velocity từng nốt khi có `<sound dynamics>`; §5.0 là bước xác nhận bắt buộc.

Đây là thiết kế của pipeline; §5.0 là bước xác nhận bằng tai và RMS rằng MuseScore thật sự dùng velocity từng nốt, trước khi code.

### 2.3 Hạ tầng params và tuning drawer đã sẵn

- `backend/app/sonify/params.py:33-120` — schema bảy knob hiện tại.
- `backend/app/sonify/params.py:405` — `active()`; `compose_params` ở `:410`.
- `backend/app/sonify/dynamics.py:41-65` — `contrast_velocity()` và `apply_contrast()` là tiền lệ scale velocity toàn cục.
- `backend/app/sonify/render.py:1272` — `apply_contrast(score)` chạy sau frame, trước humanize.
- `src/musicalize/TuningPanel.tsx:301` — drawer render group/field động từ schema.
- `scripts/gen_params_schema.py` — sinh schema cho backend và app.

Thêm ba field là mở rộng đúng chỗ, không phải dựng cơ chế mới.

---

## 3. Quyết định đã chốt

| # | Quyết định | Giá trị |
|---|---|---|
| 1 | Ba knob | `guitar_high`, `guitar_mid`, `guitar_bass` |
| 2 | Khoảng | `-8 – +8` (velocity) |
| 3 | Bước | `1` |
| 4 | Default | `0` |
| 5 | Mute | Không làm; `-8` là mức nhỏ nhất |
| 6 | Bè trung | Gộp `support` (voice 2 và 4) thành một knob |
| 7 | Thời điểm áp dụng | Như các knob hiện tại: đổi giá trị, **lần Play tiếp theo** mới render |
| 8 | DFI | Tính **trước** balance; balance là bước xuất âm thanh, không đổi metric dữ liệu |
| 9 | Phạm vi | Chỉ `score.variant == "guitar"`; không áp cho ensemble `guitar` của Minimalist |
| 10 | Schema | Giữ `SCHEMA_VERSION = 2`; key mới là optional, thiếu thì lấy default |
| 11 | Cache | Dùng `params_hash` sẵn có; Default vẫn không có hậu tố |
| 12 | Timbre mid/bass | Giữ range `-8 – +8` velocity; hint khi `> +4`; A/B `0 / +4 / +8`; offset dịch cả thang snap, nốt `69–73` có thể lên `77–78`; **v1 không cap** |

---

## 4. Thiết kế

### 4.1 Ba field trong schema

Thêm vào `backend/app/sonify/params.py`:

| Key | Nhãn UI | Nhóm | Min | Max | Step | Default | Unit | Mô tả |
|---|---|---|---:|---:|---:|---:|---|---|
| `guitar_high` | Bè cao | `guitar` | -8 | +8 | 1 | 0 | `""` | Độ lệch velocity của bè cao (giai điệu). 0 là bản hiện tại. |
| `guitar_mid` | Bè trung | `guitar` | -8 | +8 | 1 | 0 | `""` | Độ lệch velocity của bè trung (các voice support). 0 là bản hiện tại. |
| `guitar_bass` | Bè bass | `guitar` | -8 | +8 | 1 | 0 | `""` | Độ lệch velocity của bè bass (ngón cái). 0 là bản hiện tại. |

Ba field đặt `signed=True` trong schema để client hiện `+4`; `paramValueText` đọc cờ này, không suy từ `step`.

Nhóm mới:

```python
GUITAR = "guitar"
GROUPS = (
    (PERFORMANCE, "Trình diễn"),
    (TEXTURE, "Sâu hơn"),
    (GUITAR, "Guitar"),
)
```

`params_schema.json` và `paramsSchema.generated.ts` sinh lại bằng `python scripts/gen_params_schema.py`.

### 4.2 Pass `apply_voice_balance()`

Đặt hàm cạnh `apply_contrast()` trong `backend/app/sonify/dynamics.py`:

```text
apply_voice_balance(score) -> Score
  nếu score.variant != "guitar": trả nguyên score
  offsets = {
      "lead":    active("guitar_high"),
      "support": active("guitar_mid"),
      "low":     active("guitar_bass"),
  }
  nếu cả ba bằng 0: trả nguyên score
  với từng field:
      velocity = int(note.velocity + offset)
      clamp 1..127
      replace(note, velocity=velocity)
```

Chi tiết:

- Chỉ đổi `velocity`; không đổi pitch, duration, voice, tie, slur, dynamic event.
- Nốt nghỉ (`midi is None`, `velocity is None`) giữ nguyên.
- `pinned` và `hairpin` cũng cộng offset; đây là mixer sau humanize, không phải humanize.
- Vì toàn bộ một field cộng cùng một offset, chuỗi tie vẫn giữ velocity bằng nhau.
- Knob là **độ lệch velocity**, không phải dB và không phải %. `+8` cộng 8 vào velocity; `-8` trừ 8.
- Offset cộng cho **toàn bộ stream sau `_clamp_guitar`**, nên không chỉ nốt `56/60`: nốt đã ở dải snap `69–73` cũng lên `77–78`. Đây là hành vi chấp nhận; nghe lại ở `+5..+8`. Max đo được khoảng `78`, còn xa trần `127`.
- Default `0` trả **cùng object** `score`, nên XML/audio Default byte-identical.

### 4.3 Thứ tự áp dụng

```text
render(spec, ctx.bpm)
  → apply_contrast()        # dynamics knob, toàn score
  → humanize()              # nốt, tie, tempo
  → compute_dfi()           # metric dữ liệu, chưa thấy balance
  → apply_voice_balance()   # ba bè guitar
  → score_to_musicxml()
  → MuseScore → ffmpeg preset → .m4a
```

**Không** đặt pass này trong `_finish()` / `apply_contrast()`.

Lý do: `backend/app/sonify/humanize.py:347-377` — `_clamp_guitar()` ép nốt viết `≤ 64` ở lại `≤ 64`, và nốt `> 64` vào dải snap. Dải snap là **69..73** cho `bach`/`classic`/`torroba` và **69..79** cho các ensemble còn lại; chỉ áp cho **attack** (`_is_attack`). Nếu cộng offset trước humanize, một nốt `72` +8 = `80` sẽ bị kéo về trần `73` (`bach`/`classic`/`torroba`) hoặc `79` (ensemble còn lại); nốt `60` +8 = `68` bị đẩy lên sàn `69`; tương quan ba bè bị đảo. Đặt sau humanize thì `_clamp_guitar` đã chạy xong, offset còn nguyên.

Hai chỗ gọi trong `backend/app/sonify/audio.py`, **cùng một mẫu**:

- Span, `:1470-1483`:
  - `if _humanize_on(values):` ở `:1472`, `score = humanize_score(...)` ở `:1473`
  - `dfi = compute_dfi(score, ...)` ở `:1474` — **đã tính xong**
  - khối `with compose_params(values):` thứ hai ở `:1481`
  - đặt `score = apply_voice_balance(score)` **ngay trước** `xml = score_to_musicxml(score)` ở `:1482`
- Recap, `:1670-1676`: cùng thứ tự; đặt ngay trước `xml = score_to_musicxml(score)` ở `:1675`.

**Không** đặt call bên trong `if _humanize_on(values):`. `_humanize_on` (`audio.py:88`) gọi `params_layers(...)[0]` (`params.py:312-316`), tức `humanize != 0 or breath != 0`. Khi người dùng kéo Humanize = 0 và Hơi thở = 0, `humanize_score()` bị bỏ qua; nếu balance nằm trong khối đó, ba knob guitar sẽ im lặng mà không báo lỗi. Test bắt buộc: `humanize = 0, breath = 0, guitar_bass = -8` vẫn đổi `low`.

Thêm comment cạnh call: `# must stay after compute_dfi: DFI reads note velocity`.

Các chỗ recompose chỉ để tính DFI (`backend/app/services/dfi.py:223,257`) **không** gọi balance, vì quyết định ở §3 mục 8: tính DFI trước balance.

### 4.4 Default parity và cache

- Ở `0`, `apply_voice_balance()` trả nguyên `score`; không có nhánh nào khác chạy.
- `DEFAULT_HASH` **đổi** vì `params_key` chứa toàn bộ field. Hash mới là `8653a4d3fcad`; test pin ở `backend/tests/test_params.py:32` và `src/musicalize/params.test.ts:51` đã cập nhật.
- Audio Default vẫn dùng tên file cũ (không hậu tố), nên không render lại nếu revision không đổi.
- Link `p=` cũ vẫn decode được vì schema giữ `2` và `normalize_params()` điền default cho key thiếu. Ba key mới nhận `0`; các knob cũ giữ nguyên giá trị trong link.
- Cache cũ: profile chỉ khác `humanize` / `breath` / `color` vẫn đi qua `legacy_layer_mark()` (`params.py:268-289`) và tái dùng `_nh` / `_nc` / `_nh_nc`, vì ba key guitar mới ở default là no-op. Chỉ profile khác `tempo`, `dynamics`, `noise`, `density`, hoặc ba knob guitar mới rơi sang `_p<hash>` và render lại một lần.
- Khi ba field khác default, `cache_mark()` tự trả `_p<hash>`; LRU hiện có xử lý.

### 4.5 UI

`src/musicalize/TuningPanel.tsx` đã nhận prop `variant` (`:516`). Cần:

- Thêm helper `visibleFields(variant)` trả `PARAM_FIELDS` trừ group `guitar` khi `variant !== 'guitar'`.
- Dùng helper đó cho **cả ba** chỗ: render group (`:301`), `changedCount()` (`:71`), và `paramSummary()` (`:74`).
- `paramSummary()` đang được gọi ở danh sách profile (`:418`) trong `ProfileTab` — component này hiện **không** nhận `variant` (`:338`, render ở `:638`). Phải truyền `variant` từ `TuningPanel` xuống `ProfileTab` và xuống `paramSummary(item.params, variant)`. Nếu chỉ lọc ở group render, profile vẫn báo “3 thay đổi” khi đang nghe Giao hưởng.
- Hint khi `> +4` cho cả ba knob: “Trên +4 đẩy nốt snap khỏi dải móng”. Ba slider dùng đúng `ParamSlider`; `paramValueText` hiện số nguyên kèm dấu `+` (`+4`, `0`, `-8`) dựa trên cờ `signed` trong schema, không suy từ `step`.
- Profile lưu/đổi tên/URL dùng nguyên cơ chế `params.ts`; không đổi logic `link.ts` / `profileStorage.ts`. Chỉ sửa comment “seven knobs” ở `params.ts:6`, `link.ts:19`, `src/api/client.ts:558` và `:833` thành “ten knobs” khi thêm field. `docs/sonify-params-profile-plan.md` là doc lịch sử, không sửa.

---

## 5. Kiểm thử

### 5.0 Bước 0 — xác nhận MuseScore tôn trọng velocity từng nốt

Đã chạy trên máy local trước khi chốt pass:

1. Từ **cùng một score** guitar `classic` (hoặc `torroba`), tạo hai bản bằng cách cộng `-8` và `+8` vào `NoteEvent.velocity` của các nốt trong `score.low` (script tạm), rồi để `score_to_musicxml()` ghi thành thuộc tính `<note dynamics="...">` và export qua `musescore_export`. Chưa cần thêm params vào schema. **Không** đụng `score.dynamics` — đó là danh sách `DynamicEvent`, không phải velocity từng nốt.
2. Đo RMS/peak hai file (`ffmpeg -af astats` hoặc `waveform_peaks_with_level`) và nghe A/B.
3. Nếu hai file giống nhau hoặc không nghe khác: MuseScore đang áp `<sound dynamics>` của part đè lên velocity từng nốt. **Dừng**, chuyển thẳng phương án B; không code tiếp pass A.
4. Nếu khác rõ: ghi lại file/kết quả vào PR rồi mới code.

Kết quả local: bass `-8 / 0 / +4 / +8` cho RMS `0.02068 / 0.02517 / 0.02784 / 0.03081` (12 bar, guitar `classic`) — MS Basic phản ứng với velocity từng nốt.

`test_recap.py:514` chỉ khoá việc chọn **MS Basic**, không chứng minh velocity từng nốt thắng dynamic của part. Bước 0 là chỗ duy nhất xác nhận điều đó bằng tai và bằng số.

### 5.1 Backend

- `normalize_params()` nhận ba key mới; thiếu key lấy `0`; ngoài khoảng bị clamp và cảnh báo.
- `schema_payload()` có group `guitar`, đúng min/max/step/default.
- `DEFAULT_HASH` mới khớp giữa Python và TypeScript.
- `apply_voice_balance()`:
  - `0` trả cùng object / cùng XML.
  - `symphony`, `jazz`, `minimalist`, `ambient` trả nguyên score dù params khác.
  - `guitar_high = -8` chỉ đổi `lead`; `support` và `low` không đổi.
  - `guitar_mid = +8` đổi cả voice 2 và 4.
  - `guitar_bass = -8` chỉ đổi `low`.
  - velocity luôn trong `1..127`.
  - tie chain vẫn cùng velocity.
  - `humanize = 0, breath = 0` + `guitar_bass = -8` vẫn đổi `low` (không bị gate bởi `if _humanize_on`); test store-level đọc XML trong exporter giả và assert hai bản khác nhau.
  - `score_to_musicxml(apply_voice_balance(score))` ghi `<note dynamics="...">` khác bản default, nên offset đến được output chứ không chỉ nằm trong `Score`.
- **Thứ tự DFI**: `dfi = compute_dfi(score)` lấy trên score **trước** balance. Test end-to-end ở tầng store: dùng exporter giả (như `test_recap`), render cùng spec hai lần chỉ khác `guitar_bass` (`0` vs `-8`), assert `dfi` trong payload **bằng nhau**; chọn score có `window_volumes` đủ để `_volume()` không trả `None`, nếu không test sẽ xanh vô nghĩa. Test này đi qua đúng thứ tự trong `audio.py`; nếu ai đảo balance lên trước `compute_dfi`, `_volume()` đọc `event.velocity` đã đổi (`backend/app/sonify/dfi.py:817-841`) và DFI sẽ khác → đỏ. Thêm comment `# must stay after compute_dfi` cạnh call.
- Span (`_render_movement`) dùng cùng mẫu call; test store-level dùng recap. Không có test span riêng (rủi ro thấp).
- `cache_mark()` khác nhau giữa hai mức balance; Default vẫn `""`.
- `python scripts/gen_params_schema.py --check` xanh.

### 5.2 Client

- `normalizeParams()` điền default cho key mới.
- `paramsKey()` khớp server.
- `readLink()` với `p` cũ (thiếu ba key): ba key mới nhận `0`, các knob còn lại giữ nguyên giá trị cũ trong link — không phải toàn bộ về Default.
- `params.test.ts:52` pin số knob `7 → 10`; sửa comment “seven knobs” ở `params.ts:6`, `link.ts:19`, `src/api/client.ts:558` và `:833`.
- `TuningPanel` ẩn group `guitar` ở variant khác, hiện ở `guitar`.
- `changedCount()` và `paramSummary()` dùng `visibleFields(variant)`; `ProfileTab` nhận `variant`, profile summary ở phòng Giao hưởng không đếm knob guitar.

### 5.3 Tai nghe

- Bước 0 đo bass `-8 / 0 / +4 / +8` trên guitar `classic` 12 bar: RMS `0.02068 / 0.02517 / 0.02784 / 0.03081`; tăng đơn điệu, không click.
- A/B mid/bass `0 / +4 / +8` vẫn là checklist tai nghe: pass cộng sau `_clamp_guitar` nên nốt snap `69–73` có thể lên `77–78`; nghe lại ở `+5..+8`. Nếu lấn, fallback cap `68` cho mid/bass, không đổi range.
- Guitar `barrios` tremolo: `guitar_mid` không làm mất tiếng tremolo.
- Guitar `villa` `thumb_cantabile`: ghi nhận bass mang giai điệu; giảm bass sẽ giảm cả câu hát ngón cái.
- Cả ba cùng `+8`: kiểm tra không clip trên file `.m4a`.

---

## 6. Phương án B — fader thật

Chỉ làm nếu cần một trong ba thứ:

1. Gain thuần, không đổi timbre.
2. Mute sạch từng bè.
3. Kéo volume khi đang phát.

Cách làm:

- Tách guitar thành **ba part** (`cao`, `trung`, `bass`), mỗi part một track riêng trong `audiosettings.json` với `volumeDb` riêng — hạ tầng đã có ở `backend/app/sonify/audio.py:817-833`.
- Hoặc render **ba stem**, client mix bằng Web Audio.

Hệ quả: đổi layout score (ba khuông), đổi `_PARTS_BY_VARIANT`, test MusicXML, thời gian render tăng, peaks/DFI phải tính lại. Không nên gộp vào v1.

---

## 7. Phạm vi và ước lượng

| Tầng | File | Việc |
|---|---|---|
| Schema | `backend/app/sonify/params.py` | Thêm 3 field + group `guitar` |
| Pass | `backend/app/sonify/dynamics.py` | `apply_voice_balance()` |
| Audio | `backend/app/sonify/audio.py` | Gọi pass ở 2 chỗ trước `score_to_musicxml()` |
| Sinh schema | `backend/app/sonify/fixtures/params_schema.json`, `src/musicalize/paramsSchema.generated.ts` | Chạy `gen_params_schema.py` |
| UI | `src/musicalize/TuningPanel.tsx` | `visibleFields(variant)`, hint mid/bass, truyền `variant` vào `ProfileTab` |
| Test | `backend/tests/test_params.py`, `backend/tests/test_params_cache.py`, test guitar/humanize, `src/musicalize/params.test.ts` | Cập nhật hash; pin `7 → 10` ở `params.test.ts:52`; sửa comment “seven knobs” ở `params.ts:6`, `link.ts:19`, `src/api/client.ts:558` và `:833`; thêm case balance và `humanize = 0` |

Ước lượng: **0.5 ngày cho Bước 0 + nghe thử**, cộng **1–1.5 ngày code**, không gồm nghe thử trên nhiều ensemble.

---

## 8. Ngoài phạm vi

- Mute từng bè.
- Tách riêng voice 2 và voice 4 của bè trung.
- Kéo volume realtime khi đang phát.
- So sánh DFI giữa các mức balance (DFI cố ý tính trước balance).
- Áp dụng cho ensemble `guitar` của Minimalist (variant `minimalist`, không phải `guitar`).
- Tự động cân bằng theo thể loại hay theo dữ liệu.

---

## 9. Rủi ro đã biết

| Rủi ro | Mức | Xử lý |
|---|---|---|
| Velocity đổi timbre, không phải gain thuần | Thấp | Pass cộng sau `_clamp_guitar`, nên cả nốt snap cũng dịch: `classic` lead `70 → 78`, support `64 → 72`, low `69 → 77`; max ~`78`, không clip. Hint khi `> +4`; A/B `0/+4/+8`; **v1 không cap**; chỉ cap `68` cho mid/bass nếu A/B fail |
| Boost cả ba cùng lúc có thể chạm trần mix | Thấp | Range `+8`; nghe thử file `.m4a`; nếu cần, thêm limiter cuối ở PR sau |
| Bass mang giai điệu ở `thumb_cantabile` | Trung bình | Ghi chú trong tài liệu; không có cách tách nếu không đổi pattern |
| DFI không phản ánh balance | Thấp | Là quyết định có chủ ý: DFI là metric dữ liệu, balance là mix |
| Field mới làm hash đổi, profile cũ render lại một lần | Thấp | Chấp nhận; profile chỉ khác humanize/breath/color vẫn dùng cache legacy; Default không đổi tên file |
| Chỉnh knob guitar rồi đổi sang thể loại khác vẫn đổi hash | Thấp | Audio không đổi; chỉ tốn một lần render. Có thể lọc khỏi hash sau nếu thấy phiền |
| DFI cache trùng khi chỉ khác balance | Thấp | DFI giống nhau nhưng `params_hash` khác; chấp nhận ở v1 |
| Group guitar hiện ở variant khác | Thấp | Lọc theo `variant` ở `TuningPanel` |
| Consumer khác đọc `schema_payload` vẫn thấy group `guitar` | Thấp | Không sao; client cũ bỏ qua field lạ, client chưa update chỉ hiện thêm group. Ghi lại để không ngạc nhiên |
