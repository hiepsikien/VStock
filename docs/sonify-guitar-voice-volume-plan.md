# Volume ba bè guitar — Kế hoạch

> **Trạng thái**: đã đối chiếu code, chưa code.
>
> **Đọc cùng**: [`sonify-params-profile-plan.md`](./sonify-params-profile-plan.md), [`musicalize-plan.md`](./musicalize-plan.md), [`sonify-instrument-sets.md`](./sonify-instrument-sets.md).
>
> **Mục tiêu**: thêm ba knob cân bằng bè **cao / trung / bass** cho variant `guitar` trong bàn tinh chỉnh, giữ `Default` bất biến, và không đổi kiến trúc render hiện tại.

---

## 1. Kết luận

Làm được với pipeline hiện tại, nhưng phải hiểu đúng bản chất:

- Pipeline guitar xuất **một file mix duy nhất** từ **một part nylon**. Không có stem, nên không thể vặn volume từng bè sau khi render.
- Ba bè đã tách sẵn trong `Score` (`lead`, `support`, `low`), và âm thanh guitar đang dựa vào **velocity từng nốt** để cân bằng. Vì vậy thêm ba hệ số velocity là đủ.
- Đây là **cân bằng velocity**, không phải gain thuần. Nó đổi cả lớp sample/timbre khi đi xa khỏi 1.0.
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

`backend/app/sonify/musicxml.py:1205-1222` — `_guitar_voices()` xếp đúng thứ tự **lead → từng voice support → low**.
`backend/app/sonify/musicxml.py:1223` — `_guitar_part()`: “One nylon part. The lead, each support voice, and the bass share the measure.”

Vì vậy ba bè không cần tách mới ở tầng dữ liệu; chúng đã là ba nhóm luồng độc lập trước khi vào MuseScore (`support` có thể là hai voice nhưng vẫn chung một knob).

### 2.2 Velocity từng nốt đang là cơ chế cân bằng thật

- `backend/app/sonify/guitar.py:53-56` — các mức cố định: `_MELODY = 64`, `_INNER = 56`, `_BASS = 60`.
- `backend/app/sonify/guitar.py:79` — `TREMOLO_BASS_TRIM = 2` hạ thumb tremolo.
- `backend/app/sonify/audio.py:874-887` — guitar cố ý **không dùng MuseSounds nylon**, vì sampler đó bỏ qua velocity từng nốt; part giữ **MS Basic** để velocity “speaks”.
- `backend/tests/test_recap.py:516-534` — `test_nylon_guitar_stays_on_ms_basic_so_note_velocities_speak` khoá hành vi này.

Đây là bằng chứng trực tiếp: giảm velocity bè bass sẽ giảm bass trong bản thu.

### 2.3 Hạ tầng params và tuning drawer đã sẵn

- `backend/app/sonify/params.py:33-120` — schema bảy knob hiện tại.
- `backend/app/sonify/params.py:398` — `active()` / `compose_params`.
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
| 2 | Khoảng | `0.75 – 1.25` |
| 3 | Bước | `0.05` |
| 4 | Default | `1.00` |
| 5 | Mute | Không làm; `0.75` là mức nhỏ nhất |
| 6 | Bè trung | Gộp `support` (voice 2 và 4) thành một knob |
| 7 | Thời điểm áp dụng | Như các knob hiện tại: đổi giá trị, **lần Play tiếp theo** mới render |
| 8 | DFI | Tính **trước** balance; balance là bước xuất âm thanh, không đổi metric dữ liệu |
| 9 | Phạm vi | Chỉ `score.variant == "guitar"`; không áp cho ensemble `guitar` của Minimalist |
| 10 | Schema | Giữ `SCHEMA_VERSION = 2`; key mới là optional, thiếu thì lấy default |
| 11 | Cache | Dùng `params_hash` sẵn có; Default vẫn không có hậu tố |

---

## 4. Thiết kế

### 4.1 Ba field trong schema

Thêm vào `backend/app/sonify/params.py`:

| Key | Nhãn UI | Nhóm | Min | Max | Step | Default | Unit | Mô tả |
|---|---|---|---:|---:|---:|---:|---|---|
| `guitar_high` | Bè cao | `guitar` | 0.75 | 1.25 | 0.05 | 1.00 | × | Hệ số velocity của bè cao (giai điệu). 1.0 là bản hiện tại. |
| `guitar_mid` | Bè trung | `guitar` | 0.75 | 1.25 | 0.05 | 1.00 | × | Hệ số velocity của bè trung (các voice support). 1.0 là bản hiện tại. |
| `guitar_bass` | Bè bass | `guitar` | 0.75 | 1.25 | 0.05 | 1.00 | × | Hệ số velocity của bè bass (ngón cái). 1.0 là bản hiện tại. |

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
  gains = {
      "lead":    active("guitar_high"),
      "support": active("guitar_mid"),
      "low":     active("guitar_bass"),
  }
  nếu cả ba bằng 1.0: trả nguyên score
  với từng field:
      velocity = int(note.velocity * gain + 0.5)   # half-up, như tempo_bpm
      clamp 1..127
      replace(note, velocity=velocity)
```

Chi tiết:

- Chỉ đổi `velocity`; không đổi pitch, duration, voice, tie, slur, dynamic event.
- Nốt nghỉ (`midi is None`, `velocity is None`) giữ nguyên.
- `pinned` và `hairpin` cũng nhân; đây là mixer sau humanize, không phải humanize.
- Vì toàn bộ một field nhân cùng hệ số, chuỗi tie vẫn giữ velocity bằng nhau.
- Default 1.0 trả **cùng object** `score`, nên XML/audio Default byte-identical.

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

Lý do: `backend/app/sonify/humanize.py:347-377` — `_clamp_guitar()` ép nốt viết `≤ 64` ở lại `≤ 64`, và nốt `> 64` vào khoảng `69..79`. Nếu nhân gain trước humanize, một bè boost từ `64` lên `80` sẽ bị kéo về `79`; boost mất gần hết tác dụng và tương quan ba bè bị đảo. Đặt sau humanize thì `_clamp_guitar` đã chạy xong, gain còn nguyên.

Hai chỗ gọi trong `backend/app/sonify/audio.py`:

- `:1472` (span) — sau `humanize_score()`, trước `score_to_musicxml()` ở `:1482`.
- `:1666` (recap) — sau `humanize_score()`, trước `score_to_musicxml()` ở `:1675`.

Các chỗ recompose chỉ để tính DFI (`backend/app/services/dfi.py:223,257`) **không** gọi balance, vì quyết định ở §3 mục 8: tính DFI trước balance.

### 4.4 Default parity và cache

- Ở `1.0`, `apply_voice_balance()` trả nguyên `score`; không có nhánh nào khác chạy.
- `DEFAULT_HASH` **sẽ đổi** vì `params_key` chứa toàn bộ field. Test đang pin `5800e09635be` (`backend/tests/test_params.py:34`, `src/musicalize/params.test.ts:51`) phải cập nhật theo hash mới.
- Audio Default vẫn dùng tên file cũ (không hậu tố), nên không render lại nếu revision không đổi.
- Link `p=` cũ vẫn decode được vì schema giữ `2` và `normalize_params()` điền default cho key thiếu. Tuy nhiên hash của profile cũ đổi, nên file non-default cũ không được tái dùng — chấp nhận một lần render lại.
- Khi ba field khác default, `cache_mark()` tự trả `_p<hash>`; LRU hiện có xử lý.

### 4.5 UI

`src/musicalize/TuningPanel.tsx` đã nhận prop `variant`. Chỉ cần:

- Lọc group `guitar` khi `variant !== 'guitar'`.
- `changedCount()` chỉ đếm field đang hiện, để profile không báo “3 thay đổi” khi đang nghe Giao hưởng.
- Không thêm hint đặc biệt; ba slider dùng đúng `ParamSlider` hiện có.
- `paramSummary` và profile lưu/đổi tên/URL dùng nguyên cơ chế `params.ts`.

Không cần sửa `link.ts`, `profileStorage.ts`, hay `params.ts` logic; tất cả đọc từ schema generated.

---

## 5. Kiểm thử

### 5.1 Backend

- `normalize_params()` nhận ba key mới; thiếu key lấy `1.0`; ngoài khoảng bị clamp và cảnh báo.
- `schema_payload()` có group `guitar`, đúng min/max/step/default.
- `DEFAULT_HASH` mới khớp giữa Python và TypeScript.
- `apply_voice_balance()`:
  - `1.0` trả cùng object / cùng XML.
  - `symphony`, `jazz`, `minimalist`, `ambient` trả nguyên score dù params khác.
  - `guitar_high = 0.75` chỉ đổi `lead`; `support` và `low` không đổi.
  - `guitar_mid = 1.25` đổi cả voice 2 và 4.
  - `guitar_bass = 0.75` chỉ đổi `low`.
  - velocity luôn trong `1..127`.
  - tie chain vẫn cùng velocity.
  - DFI của cùng score không đổi trước/sau balance.
- `cache_mark()` khác nhau giữa hai mức balance; Default vẫn `""`.
- `python scripts/gen_params_schema.py --check` xanh.

### 5.2 Client

- `normalizeParams()` điền default cho key mới.
- `paramsKey()` khớp server.
- `readLink()` với `p` cũ (thiếu ba key) mở đúng Default.
- `TuningPanel` ẩn group `guitar` ở variant khác, hiện ở `guitar`.
- `changedCount()` không đếm field ẩn.

### 5.3 Tai nghe

- Guitar `classic` và `torroba`: bass `0.75`, `1.00`, `1.25` nghe rõ ba mức, không có click.
- Guitar `barrios` tremolo: `guitar_mid` không làm mất tiếng tremolo.
- Guitar `villa` `thumb_cantabile`: ghi nhận bass mang giai điệu; giảm bass sẽ giảm cả câu hát ngón cái.
- Cả ba cùng `1.25`: kiểm tra không clip trên file `.m4a`.

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
| UI | `src/musicalize/TuningPanel.tsx` | Ẩn group theo variant, lọc `changedCount()` |
| Test | `backend/tests/test_params.py`, `backend/tests/test_params_cache.py`, test guitar/humanize, `src/musicalize/params.test.ts` | Cập nhật hash và thêm case balance |

Ước lượng: **1–2 ngày**, không gồm nghe thử trên nhiều ensemble.

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
| Velocity đổi timbre, không phải gain thuần | Trung bình | Range hẹp `0.75–1.25`; ghi rõ trong mô tả UI |
| Boost cả ba cùng lúc có thể chạm trần mix | Thấp | Range `1.25`; nghe thử file `.m4a`; nếu cần, thêm limiter cuối ở PR sau |
| Bass mang giai điệu ở `thumb_cantabile` | Trung bình | Ghi chú trong tài liệu; không có cách tách nếu không đổi pattern |
| DFI không phản ánh balance | Thấp | Là quyết định có chủ ý: DFI là metric dữ liệu, balance là mix |
| Field mới làm hash đổi, profile cũ render lại một lần | Thấp | Chấp nhận; Default không đổi tên file |
| Chỉnh knob guitar rồi đổi sang thể loại khác vẫn đổi hash | Thấp | Audio không đổi; chỉ tốn một lần render. Có thể lọc khỏi hash sau nếu thấy phiền |
| DFI cache trùng khi chỉ khác balance | Thấp | DFI giống nhau nhưng `params_hash` khác; chấp nhận ở v1 |
| Group guitar hiện ở variant khác | Thấp | Lọc theo `variant` ở `TuningPanel` |
