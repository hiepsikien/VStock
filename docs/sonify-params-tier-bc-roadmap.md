# Tầng B/C của parameter profile — Lộ trình và hạng mục triển khai

> **Trạng thái**: đề xuất, đã đối chiếu code ngày 2026-11-03, chưa code.
>
> **Đọc cùng**: [`sonify-params-profile-plan.md`](./sonify-params-profile-plan.md), [`musicalize-plan.md`](./musicalize-plan.md), [`sonify-humanize-preset-plan.md`](./sonify-humanize-preset-plan.md), [PR #137 — volume ba bè guitar](https://github.com/hiepsikien/VStock/pull/137), [PR #34 — giọng gốc và chuyển giọng](https://github.com/hiepsikien/VStock/pull/34).
>
> **Mục tiêu**: mở rộng bàn tinh chỉnh từ 7 knob tầng A sang các knob tầng B (hòa âm, vùng âm, khung/dáng) và tầng C (kỹ thuật guitar, nhịp đổi hợp âm), mà vẫn giữ `Default` bất biến, cache/DFI nhất quán, và không biến phòng nghe thành DAW.

---

## 0. Kết luận điều hành

Tầng A đã là một nền đúng: schema một nguồn, hash canonical, cache theo `params_hash`, profile local, URL chia sẻ, drawer/sheet. Việc tiếp theo **không nên** là mở ngay form bars/sections hay trọng số Viterbi. Ba lý do:

1. **Thiếu vòng phản hồi.** Chưa có A/B, nên người dùng không nghe ra tác dụng của một knob mới mà không phải đổi profile rồi phát lại từ đầu. Càng mở nhiều knob, thiếu A/B càng đắt.
2. **Schema hiện tại chỉ có số.** `ParamField` trong `backend/app/sonify/params.py` chỉ có `minimum/maximum/step`, nên không thể biểu diễn “Tiết nhịp”, “Giọng”, “Kỹ thuật”, “Dáng”. Cần schema v3 có `choice`/`toggle` trước khi thêm knob rời rạc.
3. **Form/meter là phần rủi ro nhất.** Nhiều chỗ còn giả định 8 eighth/bar, 30 bar, 34 bar; `LIQUIDITY_WINDOWS`, guitar pattern và DFI trace đều bám vào đó. Làm form trước khi có A/B và schema v3 sẽ rất dễ tạo bản nghe lạc mà không ai phát hiện.

**Thứ tự đề xuất**:

```text
A3 (A/B + miền áp dụng + guitar balance)
  → B0 (schema v3, chưa đổi âm thanh)
  → B1 (harmony + register)
  → C1 (guitar technique)
  → C2 (Viterbi motion)
  → B2/B3 (frame, meter hẹp, key/form nếu có nhu cầu)
  → D (profile server, auth, AI)
```

Ước lượng thô cho B1 + C1 + C2: **7–10 tuần** cho một dev backend kiêm frontend, gồm test và nghe thử. Làm cả B2/B3: thêm **4–6 tuần**. D: **4–6 tuần**.

---

## 1. Hiện trạng

### 1.1 Tầng A đã có

| Thành phần | Trạng thái |
|---|---|
| Schema | `SCHEMA_VERSION = 2`, 7 field đều `number` trong `backend/app/sonify/params.py` |
| Canonical hash | `params_key()` / `params_hash()`, `DEFAULT_HASH = 5800e09635be` đang được pin trong test |
| Cache | `cache_mark()` trả `""` cho Default, `_nh/_nc/_nh_nc` cho legacy, `_p<hash>` cho profile khác |
| Context | `compose_params()` ContextVar, đã dùng trong `audio.py` và `services/dfi.py` |
| DFI | `_recap_key` / `_movement_key` có `params_hash` cho bản `_p<hash>`; `dfiParamsHash` là field riêng |
| API | `/sonify/params/schema`, `/validate`, `/presets`; generator `scripts/gen_params_schema.py` |
| UI | `TuningPanel.tsx` render group/field động; profile local; URL `p=`; legacy `h/c` |
| Preset | Default, Gần, Ấm, Sống, Dày |

### 1.2 Khoảng trống cho tầng B/C

| # | Khoảng trống | Hệ quả |
|---|---|---|
| 1 | Schema chỉ có `number` | Không thể thêm “Tiết nhịp”, “Giọng”, “Kỹ thuật”, “Dáng” mà không nhét index số vào UI |
| 2 | Không có `appliesTo` | `TuningPanel` render mọi group; `changedCount()` đếm cả field không liên quan; profile báo “3 thay đổi” khi đang nghe thể loại khác |
| 3 | Không có A/B | Muốn so sánh phải đổi profile, phát lại, tua lại; không đánh giá được knob mới |
| 4 | Không có tier flag | Kill switch `VSTOCK_SONIFY_PARAMS` tắt cả A; chưa thể bật B mà vẫn giữ A khi rollback |
| 5 | Chưa audit form/meter | `EIGHTHS_PER_BAR`, `LIQUIDITY_WINDOWS`, hardcoded bar count trong guitar pattern, DFI trace |
| 6 | Chưa có macro hoá Viterbi | `TRANSITION_WEIGHT`, `SEVENTH_TENSION_COST`, các penalty đang là hằng số rải rác |

### 1.3 Vì sao không nhảy thẳng vào form/Viterbi

- **A/B là đòn bẩy lớn nhất.** Nó biến “thử knob” từ một hành động rời room thành một thao tác một giây. Không có nó, mọi knob B/C đều khó đánh giá.
- **Schema v3 là cửa một lần.** Nếu thêm từng knob rồi bump schema nhiều lần, mỗi lần đổi `DEFAULT_HASH`, link cũ và profile cũ lại phải migrate. Nên khai báo trước toàn bộ key B/C trong một lần bump.
- **Form/meter chạm nhiều bất biến.** Chúng đổi độ dài bài, số bar, `frame_seconds`, mapping giá, guitar pattern, DFI trace. Đây là việc có thể làm, nhưng phải tách khỏi B1 và có test riêng.

---

## 2. Nguyên tắc thiết kế

1. **Default parity tuyệt đối.** Mọi knob mới ở default phải cho score/MusicXML **byte-identical** với hiện tại. Audio Default chỉ đổi khi có revision có chủ ý.
2. **Macro knob, không expose raw weight.** Không đưa `TRANSITION_WEIGHT`, `SEVENTH_TENSION_COST`, chuỗi FFmpeg hay trọng số Viterbi lên UI. Chỉ đưa các trục người nghe hiểu: “Màu hòa âm”, “Vùng âm”, “Kỹ thuật”, “Nhịp hòa âm”.
3. **Mỗi knob có miền áp dụng.** Thêm `appliesTo` (variant/ensemble/span) vào schema. Field không áp dụng phải ẩn/disable, không tính vào “số thay đổi”, và nên được đưa về default khi đổi variant để tránh hash khác mà tai nghe y hệt.
4. **Một lần bump schema v3.** Khai báo trước toàn bộ key B/C, kể cả key còn tắt sau tier flag. `p` schema 2 vẫn phải đọc được và tự nâng lên 3.
5. **A/B trước khi mở B/C.** A/B là điều kiện để đánh giá `harmony`, `register`, `technique`.
6. **Rollout theo tầng.** Server trả `enabledTiers`; client ẩn group ngoài tầng được bật. Default vẫn là `A`.
7. **Không thay đổi bản sắc dữ liệu nếu chưa có chủ ý.** `key` và form là thay đổi bản sắc bài; chỉ làm sau khi có quyết định sản phẩm rõ ràng.
8. **Playability là cổng, không phải gợi ý.** Mọi knob guitar phải đi qua `assert_playable`; nếu không playable thì fallback auto + warning, không render bản vỡ.

---

## 3. Bản đồ knob đề xuất

### 3.1 Tầng A3 — bổ sung trước khi sang B

| Key | Nhãn | Kiểu | Khoảng | Default | Phạm vi | Ghi chú |
|---|---|---|---:|---:|---|---|
| `guitar_high` | Bè cao | number | 0.75–1.25, step .05 | 1.00 | guitar | Theo PR #137 |
| `guitar_mid` | Bè giữa | number | 0.75–1.25, step .05 | 1.00 | guitar | Gộp support voice 2 và 4 |
| `guitar_bass` | Bè bass | number | 0.75–1.25, step .05 | 1.00 | guitar | Áp sau humanize, trước MusicXML |

### 3.2 Tầng B/C — knob mới

| Key | Nhãn | Kiểu | Giá trị | Default | Phạm vi | Wave | Ý nghĩa |
|---|---|---|---|---|---:|---|---|---|
| `harmony` | Màu hòa âm | number | 0.00–2.00, step .05 | 1.00 | tất cả | B1 | 0 = triad, không borrowed/7th; 1 = hiện tại; 2 = nhiều 7th/9th/borrowed hơn |
| `register` | Vùng âm | number | 0.00–2.00, step .05 | 1.00 | tất cả; guitar giới hạn | B1 | 0 = thấp/ấm; 1 = hiện tại; 2 = cao/sáng. Dịch bounds vài semitone, không đổi giọng |
| `technique` | Kỹ thuật | number | 0.00–2.00, step .05 | 1.00 | guitar | C1 | 0 = dễ/arpeggio/chorale; 1 = hiện tại; 2 = điêu luyện/tremolo/dance |
| `motion` | Nhịp hòa âm | number | 0.00–2.00, step .05 | 1.00 | tất cả | C2 | 0 = giữ hợp âm lâu; 1 = hiện tại; 2 = đổi hợp âm dồn dập |
| `frame` | Khung | choice | auto / 0 / ngắn / dài | auto | span dài `1M–1Y` | B2 | Độ dài warm-up/cool-down; 1D giữ nguyên |
| `meter` | Tiết nhịp | choice | auto / 4/4 / 3/4 / 6/8 / 12/8 | auto | hẹp, nơi đã có retarget | B2 | Chỉ mở cho jazz/guitar trước; chưa mở toàn cục |
| `key` | Giọng | choice | auto / Eb / Bb / C / D / A | auto | tùy quyết định | B3 | Nên rebase trên PR #34; không làm nếu chưa chốt bản sắc giọng |
| `form` | Dáng | choice | compact / standard / extended | standard | 1D? | B3 | Chỉ sau discovery; cần resample giá và audit bar count |

**Không đưa vào đợt này**: raw Viterbi weights, chuỗi FFmpeg, số bar tùy ý, editor từng nốt, realtime đổi knob khi đang phát.

---

## 4. Lộ trình theo wave

| Wave | Pha | Nội dung | Kết quả | Ước lượng | Rủi ro |
|---|---|---|---|---|---|
| **1** | A3 | A/B MVP, `appliesTo`, guitar voice balance, tier flag | So sánh được A/B; UI không hiện knob sai thể loại | 2–3 tuần | Thấp |
| **2** | B0 | Schema v3, migration, UI choice/toggle, generator | Nền cho mọi knob B/C; chưa đổi âm thanh | 1.5–2 tuần | Trung bình |
| **3** | B1 | `harmony`, `register` | 2 macro knob tạo khác biệt rõ về hòa âm và vùng | 3–4 tuần | Trung bình |
| **4** | C1 | `technique`, guard playability | Guitar có “độ điêu luyện” mà vẫn chơi được | 2–3 tuần | Trung bình |
| **5** | C2 | `motion` | Điều khiển nhịp đổi hợp âm | 2 tuần | Trung bình |
| **6** | B2/B3 | `frame`, `meter` hẹp, `key`/`form` nếu có nhu cầu | Cấu trúc bài sâu hơn | 3–6 tuần | Cao |
| **7** | D | Profile server/auth, AI sinh profile, DFI xuyên profile | Cá nhân hóa và vận hành | 4–6 tuần | Cao |

Có thể dừng sau Wave 3 hoặc 4. Wave 6 chỉ nên làm sau khi A/B cho thấy người dùng thực sự đụng đến cấu trúc bài.

---

## 5. Hạng mục triển khai

### Wave 1 — A3: hoàn thiện tầng A

| ID | Hạng mục | Việc chính | AC |
|---|---|---|---|
| A3.1 | A/B MVP | A = `heardParams`, B = draft/saved; toggle cạnh transport; hai nguồn audio/peaks; giữ nguyên playhead; chưa cần crossfade đồng thời | Chuyển A↔B không mất vị trí; peaks khớp tiếng; không đổi layout |
| A3.2 | Miền áp dụng | Thêm `appliesTo` vào schema; `TuningPanel` lọc group; `changedCount()` chỉ đếm field hiện; clear field khi đổi variant | Nghe Giao hưởng không thấy knob guitar; profile không báo “3 thay đổi” oan |
| A3.3 | Guitar voice balance | Làm theo PR #137 (`volume ba bè guitar`): 3 knob, chỉ guitar | Default 1.0 trả cùng score; guitar vẫn `assert_playable` |
| A3.4 | Tier flag | `enabledTiers` trong `/params/schema`; env `VSTOCK_SONIFY_PARAMS_TIER`; client ẩn group ngoài tầng | Tắt B không ảnh hưởng A; rollback không cần deploy client |
| A3.5 | Test | A/B, URL, profile, group filtering, legacy `h/c` | `test:musicalize` + backend pass |

**Ghi chú A/B**: MVP là “đổi nguồn, seek cùng vị trí”, không phải hai player chạy song song. Làm bản đồng thời sau nếu cần. State nên đặt ở `MusicalizeApp`/`TuningProvider`, không nhân đôi trong `LiveRoom` và `ReplayRoom`.

### Wave 2 — B0: nền schema v3

| ID | Hạng mục | Việc chính |
|---|---|---|
| B0.1 | Kiểu field | `ParamField` thêm `kind: number/choice/toggle`, `choices`, `auto`, `appliesTo`, `tier`; giữ `default` kiểu tương ứng |
| B0.2 | Normalize/hash | Canonical hoá mixed type; field thiếu lấy default; field ngoài tier bị ép default; hash vẫn chỉ trên `schema + params` |
| B0.3 | Migration | `decode_params` nhận schema 2 và 3; profile store v2 → v3; `writeLink` ghi schema 3; test link cũ |
| B0.4 | Generator/UI | `gen_params_schema.py` sinh type mới; thêm `ChoiceRow`, `ToggleRow`; group collapse; tab “Sâu hơn” hoặc tab thứ ba |
| B0.5 | Test hợp đồng | `DEFAULT_HASH` mới; schema `--check`; v2 link round-trip; profile import/export |

**Không đổi âm thanh ở B0.** Đây là pha bắt buộc trước mọi knob B/C.

### Wave 3 — B1: hòa âm & vùng âm

| ID | Hạng mục | Việc chính | AC |
|---|---|---|---|
| B1.1 | `harmony` | Lọc catalog và scale `SEVENTH_TENSION_COST`/borrowed bias trong `form.py`; 0 cấm 7th/9th/borrowed; 2 mở tối đa trong catalog hiện có | Default sequence identical; `harmony=0` không có 7th/9th/borrowed; `harmony=2` nhiều màu hơn trên corpus cố định |
| B1.2 | `register` | Scale các bound trong `keys.Register`; guitar kẹp ±2 semitone và chạy `assert_playable`; fallback auto + warning nếu không playable | Default identical; cực trị vẫn playable; DFI đổi đúng |
| B1.3 | UI | Label “Đơn giản / Chuẩn / Phong phú”, “Thấp / Chuẩn / Cao”; help text; A/B | Người dùng hiểu knob mà không cần đọc docs |
| B1.4 | Test | Default parity, catalog vocabulary, all variants/ensembles, guitar playability, DFI | Không có regression ngoài profile mới |

**Ghi chú**: `register` độc lập với `key`. Nếu PR #34 (giọng gốc/chuyển giọng) merge trước, `register` chỉ dịch biên độ, không chọn giọng; tránh đụng `KEY_RING`.

### Wave 4 — C1: guitar technique

| ID | Hạng mục | Việc chính | AC |
|---|---|---|---|
| C1.1 | `technique` | Chỉ áp dụng `variant === "guitar"`; override `_dominant_pattern`/`_patterns` qua whitelist theo ensemble (`classic`, `villa`, `barrios`, `brouwer`, `bach`, `torroba`) | Không chọn pattern ngoài whitelist |
| C1.2 | Fallback | Nếu pattern được chọn không playable hoặc sai meter/BPM, fallback pattern auto + warning `technique_fallback` | Không có tổ hợp nào raise `Unplayable` |
| C1.3 | `position` (optional) | Thế tay thấp/chuẩn/cao; chỉ làm nếu `technique` ổn định | Không phá `_playable` |
| C1.4 | Test | Ma trận ensemble × character × span × technique; chạy `assert_playable` cho tất cả | Default 1.0 trả cùng score |

### Wave 5 — C2: Viterbi motion

| ID | Hạng mục | Việc chính | AC |
|---|---|---|---|
| C2.1 | `motion` | Scale stay penalty, single-bar change penalty, extended stay penalty trong `plan_markov_chords`; không expose raw weight | Default sequence identical |
| C2.2 | Test | Corpus cố định; `motion=0` ít đổi hơn 1.0; `motion=2` nhiều hơn; không sinh hợp âm ngoài catalog | Quan hệ đơn điệu, không slot lỗi |
| C2.3 | Audit | Nghe thử 5 variant ở 0/1/2; ghi nhận progression lạ | Không có progression phá thể loại |

### Wave 6 — B2/B3: khung, tiết nhịp, dáng

| ID | Hạng mục | Phạm vi an toàn | Rủi ro |
|---|---|---|---|
| B2.1 | `frame` | auto / không khung / ngắn / dài, chỉ cho span dài `1M–1Y`; 1D giữ nguyên | Trung bình |
| B2.2 | `meter` | Chỉ mở nơi đã có retarget: jazz swing, guitar torroba; chưa mở 4/4→3/4 toàn cục | Cao |
| B2.3 | `form` | Discovery: compact/standard/extended; cần resample giá, audit `LIQUIDITY_WINDOWS`, guitar pattern hardcoded bar count, DFI trace | Rất cao |
| B2.4 | `key` | Optional; rebase trên PR #34; dùng transpose tương đối thay vì đổi identity tuyệt đối; guitar phải playable | Cao |

**Khuyến nghị**: làm B2.1 trước; B2.2 chỉ sau khi có test duration/chart/DFI; B2.3 và `key` chỉ làm nếu A/B cho thấy nhu cầu.

### Wave 7 — D: sau khi B/C ổn định

| ID | Hạng mục | Ghi chú |
|---|---|---|
| D1 | Profile server/auth | Chuyển profile local lên server, giữ schema/hash; quota và migration |
| D2 | AI sinh profile | AI chỉ trả JSON params; validate qua `/params/validate`; không nhận code/FFmpeg |
| D3 | DFI xuyên profile | So sánh corpus giữa các profile; hiện chỉ Default |
| D4 | Community preset | Chia sẻ/duyệt preset; có thể làm trước D1 nếu chỉ là file tĩnh |

---

## 6. Sprint đầu tiên

Nếu bắt đầu ngay, đề xuất 2 tuần:

| Ngày | Việc |
|---|---|
| 1–2 | Chốt semantics A/B MVP; thiết kế state `A/B` trong `MusicalizeApp`/`TuningProvider` |
| 3–5 | A/B MVP: hai nguồn audio/peaks, toggle, giữ playhead, test |
| 6–7 | `appliesTo` + lọc group + `changedCount()`; ẩn knob guitar khi không phải guitar |
| 8–9 | Guitar voice balance (nếu chưa ship) hoặc spike schema v3 |
| 10 | Test, cập nhật docs, viết ADR cho schema v3 |

Sau sprint này sẽ có dữ liệu thật để quyết định B1 có đáng làm tiếp hay không.

---

## 7. Test và tiêu chí nghiệm thu

### 7.1 Backend

- `test_params.py`: schema v3, default hash mới, normalize mixed type, `--check` không drift.
- `test_params_migration.py` (mới): decode `p` schema 2; profile store v2; hash của profile cũ đổi một lần, Default vẫn `""`.
- `test_harmony.py` (mở rộng): `harmony=0/1/2`; default sequence identical; không có hợp âm ngoài catalog.
- `test_keys.py`/`test_params.py`: `register` cực trị; guitar playable.
- `test_sonify_guitar.py`: ma trận `technique`; `assert_playable` cho mọi tổ hợp.
- `test_dfi.py`: DFI key có `params_hash` cho mọi knob mới; Default/legacy giữ tuple cũ.
- `test_params_cache.py`: `cache_mark()` đúng; prune/LRU không xoá bản mới.

### 7.2 Frontend

- `params.test.ts`: normalize/encode/decode mixed type; default hash; migration.
- `link.test.ts`: `p` schema 2 vẫn mở; `writeLink` ghi schema 3; `p` xuất hiện ở audio và peaks.
- `TuningPanel` test: group ẩn theo variant; `changedCount()` chỉ đếm field hiện; choice/toggle hoạt động; A/B toggle giữ playhead.
- `profileStorage` test: profile cũ v2 đọc được, ghi ra v3.

### 7.3 Nghe thử

- Mỗi knob mới: nghe 0 / 0.5 / 1 / 1.5 / 2 trên 5 variant, ít nhất một ensemble mỗi variant.
- Guitar: thêm 6 ensemble; kiểm tra tremolo, campanella, thumb cantabile.
- A/B: chuyển qua lại khi đang phát, không click, không lệch nhịp.

### 7.4 Definition of done

- Default parity: score/MusicXML byte-identical; audio Default không đổi tên file.
- Schema `--check` xanh; `DEFAULT_HASH` pin đúng.
- Link `p` cũ và mới round-trip; profile cũ migrate.
- Không có cache collision; prune/LRU bounded.
- Guitar không raise `Unplayable` ở mọi tổ hợp knob.
- Docs cập nhật; có ghi chú rollback bằng tier flag.

---

## 8. Rủi ro và cách giảm

| Rủi ro | Cách giảm |
|---|---|
| Default lệch tiếng | Snapshot score/MusicXML; test parity; tier flag; không bump revision nếu không cần |
| Guitar vỡ thế tay | `assert_playable` làm cổng; fallback auto + warning; test ma trận |
| Schema v3 làm hỏng link cũ | `decode_params` nhận schema 2; test round-trip; profile store migration |
| `harmony`/`motion` ra progression lạ | Corpus audit; test bất biến; default parity; A/B nghe thử |
| Form/meter làm lệch chart/DFI | Chỉ mở nơi đã có retarget; test `frame_seconds`, duration, DFI trace |
| UI quá tải | Group collapse, tab “Sâu hơn”, chỉ hiện field áp dụng, A/B thay vì bắt nghe lại |
| Cache phình | LRU hiện có; có thể giảm `VSTOCK_PARAMS_CACHE_MAX` cho B/C |
| ContextVar rò rỉ | Giữ pattern `compose_params` hiện tại; test async/thread |
| Trùng việc với PR #34 | `register` chỉ dịch biên độ; `key` rebase trên plan giọng gốc; không tự tạo `KEY_RING` thứ hai |

---

## 9. Quyết định cần chốt

1. **A/B trước hay B1 trước?** Đề xuất A/B trước. Nếu muốn thấy knob mới sớm, có thể làm song song B0 + A/B.
2. **Guitar có phải ưu tiên?** Nếu đúng, đưa C1 lên ngay sau B1; nếu không, làm C2 trước.
3. **Form/meter/key có thật sự cần?** Đây là phần đắt và rủi ro nhất. Nếu mục tiêu chỉ là “nghe khác đi”, B1 + C1 + C2 đã đủ sâu; form nên để sau khi có dữ liệu A/B.
4. **Profile dùng chung hay theo variant?** V1 đang dùng chung. Nếu knob guitar chỉ áp dụng cho guitar, cần chốt có cho phép profile “lai” hay tự tách profile theo variant.
5. **Có cần server profile trong quý này?** Nếu chưa, giữ local và dùng URL chia sẻ; D để sau.

---

## 10. Việc không làm trong đợt này

- Không expose raw trọng số Viterbi, chuỗi FFmpeg, biểu thức, đường dẫn file.
- Không cho nhập số bar/section tùy ý trước khi có resample và audit DFI.
- Không đổi bản sắc giọng mặc định của từng mã nếu chưa có quyết định sản phẩm.
- Không làm editor từng nốt, mixer đa stem, hay realtime đổi knob khi đang phát.
- Không làm auth/server profile trước khi A/B và B1 ổn định.
