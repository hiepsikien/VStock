# Tầng B/C của parameter profile — Lộ trình và hạng mục triển khai

> **Trạng thái**: đề xuất v2, đã xử lý review ngày 2026-11-03, chưa code.
>
> **Đọc cùng**: [`sonify-params-profile-plan.md`](./sonify-params-profile-plan.md), [`musicalize-plan.md`](./musicalize-plan.md), [`sonify-humanize-preset-plan.md`](./sonify-humanize-preset-plan.md), [PR #137 — volume ba bè guitar](https://github.com/hiepsikien/VStock/pull/137), [PR #34 — giọng gốc và chuyển giọng](https://github.com/hiepsikien/VStock/pull/34).
>
> **Mục tiêu**: mở rộng bàn tinh chỉnh từ 7 knob tầng A sang các knob tầng B (hòa âm, vùng âm, khung) và tầng C (kỹ thuật guitar, nhịp đổi hợp âm), mà vẫn giữ `Default` bất biến, cache/DFI nhất quán, và không biến phòng nghe thành DAW.

---

## 0. Quyết định đã chốt

Bảy điểm dưới đây chốt hướng triển khai. Các mục còn mở nằm ở §9.

| # | Quyết định |
|---|---|
| 1 | **A/B chỉ làm ở `ReplayRoom`**, và là **score-aware**: so sánh cả audio, peaks, score/MusicXML, DFI và chart. `LiveRoom` không có playhead để giữ; A/B ở live là việc sau, hành vi là restart stream. |
| 2 | **B là draft, không auto-save.** Preview B không gọi `planPlayParams`, không tạo profile. Chỉ lưu khi người dùng bấm `Lưu`. |
| 3 | **Link `p` tiếp tục ghi schema 2 trong giai đoạn chuyển tiếp.** Server và client mới đọc cả schema 2 và 3; app cũ đọc schema 2, giữ knob A và bỏ qua field B/C lạ. Khi app floor hỗ trợ v3 mới đổi writer sang schema 3. |
| 4 | **`appliesTo` enforce ở client, server chỉ cảnh báo.** Hash **không phụ thuộc variant/ensemble/span**. Không xoá giá trị đã lưu khi đổi variant; chỉ tính `effectiveParams` cho lần render. |
| 5 | **Bỏ `form` và `key` khỏi bảng knob chốt.** `form` để discovery sau A/B; `key` chờ PR #34 và quyết định sản phẩm về bản sắc giọng. |
| 6 | **Guitar voice (3 knob) gộp vào lần bump schema v3.** Không ship riêng trên schema 2 để tránh đổi `DEFAULT_HASH` hai lần. |
| 7 | **Tier flag tách khỏi fixture.** Fixture committed luôn chứa đủ tier; endpoint runtime mới overlay env. `VSTOCK_SONIFY_PARAMS_TIER` dạng `A`, `A,B`, `A,B,C`; mặc định `A`; token lạ bị bỏ qua kèm log. |

**Hệ quả của #6**: nếu code guitar voice đã có trong working tree, giữ nhánh nháp và rebase sau khi B0 xong, hoặc revert phần schema khỏi nhánh đó. Không merge guitar voice vào `main` trước B0.

---

## 1. Hiện trạng

### 1.1 Tầng A đã có

> Nếu guitar voice đã merge trước tài liệu này, §1.1 sẽ có 10 field và `DEFAULT_HASH` khác; các quyết định còn lại không đổi. Kiểm tra lại `SCHEMA_VERSION` và hash pin trước khi bắt đầu B0.

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
| 1 | `ParamField` chỉ mô tả số; `schema_payload()` hardcode `"type": "number"` | Không thể thêm “Tiết nhịp”, “Kỹ thuật”, “Dáng” mà không nhét index số vào UI. Điểm chặn là `schema_payload()` và type generated TS, không chỉ `minimum/maximum/step` |
| 2 | Không có `appliesTo` | `TuningPanel` render mọi group; `changedCount()` đếm cả field không liên quan; profile báo “3 thay đổi” khi đang nghe thể loại khác |
| 3 | Không có A/B | Muốn so sánh phải đổi profile, phát lại, tua lại; không đánh giá được knob mới |
| 4 | Không có tier flag | Kill switch `VSTOCK_SONIFY_PARAMS` tắt cả A; chưa thể bật B mà vẫn giữ A khi rollback |
| 5 | Chưa audit form/meter | `EIGHTHS_PER_BAR`, `LIQUIDITY_WINDOWS`, hardcoded bar count trong guitar pattern, DFI trace |
| 6 | Chưa có macro hoá Viterbi | `TRANSITION_WEIGHT`, `SEVENTH_TENSION_COST`, các penalty đang là hằng số rải rác |
| 7 | Canonical encoder client giả định number | `pythonNumber(value)` cho mọi key; string/bool sẽ tạo JSON sai và hash lệch |
| 8 | Migration profile store dùng `< SCHEMA_VERSION` | Chỉ bump version sẽ biến profile v2 thành “schema 1”, nhân `noise` thêm lần nữa |
| 9 | Link writer chưa có version negotiation | App cũ gặp schema 3 sẽ reject và im lặng mở Default |

### 1.3 Vì sao không nhảy thẳng vào form/Viterbi

- **A/B là đòn bẩy lớn nhất.** Nó biến “thử knob” từ một hành động rời room thành một thao tác một giây. Không có nó, mọi knob B/C đều khó đánh giá.
- **Schema v3 là cửa một lần.** Nếu thêm từng knob rồi bump schema nhiều lần, mỗi lần đổi `DEFAULT_HASH`, link cũ và profile cũ lại phải migrate. Guitar voice vì vậy gộp vào v3.
- **Form/meter chạm nhiều bất biến.** Chúng đổi độ dài bài, số bar, `frame_seconds`, mapping giá, guitar pattern, DFI trace. Đây là việc có thể làm, nhưng phải tách khỏi B1 và có test riêng.

---

## 2. Nguyên tắc thiết kế

1. **Default parity tuyệt đối.** Mọi knob mới ở default phải cho score/MusicXML **byte-identical** với hiện tại. Audio Default chỉ đổi khi có revision có chủ ý.
2. **Macro knob, không expose raw weight.** Không đưa `TRANSITION_WEIGHT`, `SEVENTH_TENSION_COST`, chuỗi FFmpeg hay trọng số Viterbi lên UI. Chỉ đưa các trục người nghe hiểu: “Màu hòa âm”, “Vùng âm”, “Kỹ thuật”, “Nhịp hòa âm”.
3. **`tier` khác `appliesTo`.**
   - `tier` là rollout toàn cục. Field ngoài tier bị ép default **trước khi hash** để audio/cache nhất quán; hash vì vậy phụ thuộc cấu hình tier.
   - `appliesTo` là ngữ cảnh âm nhạc (variant/ensemble/span). Client tính `effectiveParams`; server cảnh báo; **không** ép default và **không** đưa context vào hash.
4. **Không xoá giá trị đã lưu.** Đổi variant chỉ đổi cách hiển thị/render, không xoá field khỏi profile. Profile dùng chung vẫn giữ nguyên dữ liệu.
5. **Một lần bump schema v3.** Khai báo trước toàn bộ key B/C, kể cả key còn tắt sau tier flag, và gộp 3 knob guitar. `p` schema 2 vẫn phải đọc được.
6. **A/B trước khi mở B/C.** A/B phải score-aware vì B1/C1/C2 đổi score, không chỉ audio.
7. **Rollout theo tầng.** Server trả `enabledTiers`; client ẩn group ngoài tầng được bật. Default vẫn là `A`.
8. **Không thay đổi bản sắc dữ liệu nếu chưa có chủ ý.** `key` và form là thay đổi bản sắc bài; chỉ làm sau khi có quyết định sản phẩm rõ ràng.
9. **Playability là cổng, không phải gợi ý.** Mọi knob guitar phải đi qua `assert_playable`; nếu không playable thì fallback auto + warning, không render bản vỡ.

---

## 3. Bản đồ knob đề xuất

### 3.1 Guitar voice — gộp vào B0

| Key | Nhãn | Kiểu | Khoảng | Default | Phạm vi | Ghi chú |
|---|---|---|---:|---:|---|---|
| `guitar_high` | Bè cao | number | 0.75–1.25, step .05 | 1.00 | guitar | Theo PR #137 |
| `guitar_mid` | Bè giữa | number | 0.75–1.25, step .05 | 1.00 | guitar | Gộp support voice 2 và 4 |
| `guitar_bass` | Bè bass | number | 0.75–1.25, step .05 | 1.00 | guitar | Áp sau `humanize()`, trước MusicXML; DFI tính trước balance |

### 3.2 Tầng B/C — knob mới

| Key | Nhãn | Kiểu | Giá trị | Default | Phạm vi | Wave | Ý nghĩa |
|---|---|---|---|---|---|---|---|
| `harmony` | Màu hòa âm | number | 0.00–2.00, step .05 | 1.00 | tất cả | B1 | 0 = tối giản trong vocabulary của variant; 1 = hiện tại; 2 = nhiều màu hơn |
| `register` | Vùng âm | number | 0.00–2.00, step .05 | 1.00 | tất cả; guitar giới hạn | B1 | 0 = thấp/ấm; 1 = hiện tại; 2 = cao/sáng. Dịch bounds, không đổi giọng |
| `technique` | Kỹ thuật | number | 0.00–2.00, step .05 | 1.00 | guitar | C1 | 0 = dễ/arpeggio/chorale; 1 = hiện tại; 2 = điêu luyện/tremolo/dance |
| `motion` | Nhịp hòa âm | number | 0.00–2.00, step .05 | 1.00 | tất cả | C2 | 0 = giữ hợp âm lâu; 1 = hiện tại; 2 = đổi hợp âm dồn dập |
| `frame` | Khung | choice | auto / 0 / ngắn / dài | auto | span dài `1M–1Y` | B2 | Độ dài warm-up/cool-down; 1D giữ `daily_frame` riêng |
| `meter` | Tiết nhịp | choice | auto / 4/4 / 3/4 / 6/8 / 12/8 | auto | hẹp, nơi đã có retarget | B2 | Chỉ mở cho đường Torroba/guitar đã có retarget; jazz swing là playback flag, không phải meter |

**Không đưa vào bảng chốt**: `key` và `form`. Hai trục này nằm ở §9 và chỉ thành knob sau khi có quyết định/discovery tương ứng.

**Không đưa vào đợt này**: raw Viterbi weights, chuỗi FFmpeg, số bar tùy ý, editor từng nốt, realtime đổi knob khi đang phát.

---

## 4. Lộ trình theo wave

| Wave | Pha | Nội dung | Kết quả | Ước lượng | Rủi ro |
|---|---|---|---|---|---|
| **1** | A3 | A/B score-aware, `appliesTo`, tier flag, telemetry | So sánh được A/B; UI không hiện knob sai thể loại; có số liệu để quyết định B2 | 2–3 tuần | Trung bình |
| **2** | B0 | Schema v3, migration, UI choice/toggle, generator, guitar voice | Nền cho mọi knob B/C; chưa đổi âm thanh Default | 2–3 tuần | Trung bình |
| **3** | B1 | `harmony`, `register` | 2 macro knob tạo khác biệt rõ về hòa âm và vùng | 3–4 tuần | Trung bình |
| **4** | C1 | `technique`, guard playability | Guitar có “độ điêu luyện” mà vẫn chơi được | 2–3 tuần | Trung bình |
| **5** | C2 | `motion` | Điều khiển nhịp đổi hợp âm | 2 tuần | Trung bình |
| **6** | B2/B3 | `frame`, `meter` hẹp, discovery `key`/`form` | Cấu trúc bài sâu hơn, nếu có nhu cầu | 3–6 tuần | Cao |
| **7** | D | Profile server/auth, AI sinh profile, DFI xuyên profile | Cá nhân hóa và vận hành | 4–6 tuần | Cao |

Ước lượng B1 + C1 + C2 = **7–9 tuần**. Có thể dừng sau Wave 3 hoặc 4. Wave 6 chỉ nên làm sau khi các gate ở §7.5 đạt.

---

## 5. Hạng mục triển khai

### Wave 1 — A3: A/B score-aware + nền vận hành

| ID | Hạng mục | Việc chính | AC |
|---|---|---|---|
| A3.1 | A/B score-aware | Chỉ `ReplayRoom`. A = `heardParams`, B = draft. Chuẩn bị đủ audio, peaks, score/MusicXML, DFI và chart cho cả hai trước khi cho toggle. Giữ **vị trí nhạc** (bar/beat hoặc fraction), không phải giây. Crossfade 120 ms; nếu nền tảng không hỗ trợ thì gap ≤150 ms và không click. Pin hai hash A/B trong phiên để prune/LRU không xoá. `LiveRoom` disable A/B; live restart stream là việc sau. URL chia sẻ A, không chia sẻ B trong V1. | Toggle không lệch nhạc; B chưa sẵn sàng thì hiện “Đang chuẩn bị B”, không đổi nguồn; không click; không mất vị trí; A/B không auto-save |
| A3.2 | `appliesTo` + effective params | Thêm `appliesTo` vào schema; client tính `effectiveParams` cho render/validation nhưng **giữ saved values**. `TuningPanel` lọc group; `changedCount()` chỉ đếm field hiện; profile có badge “có thay đổi ẩn”. Server nhận context ở `/validate` và endpoint render để cảnh báo `inapplicable`, nhưng không ép default và không đưa context vào hash. | Đổi variant không xoá profile; nghe Giao hưởng không thấy knob guitar; hash không đổi chỉ vì variant |
| A3.3 | Tier flag | `enabledTiers` trong schema runtime; env `VSTOCK_SONIFY_PARAMS_TIER` dạng `A`, `A,B`, `A,B,C`, mặc định `A`; token lạ bỏ qua + log. Fixture committed luôn đủ tier. Server ép key ngoài tier về default trước hash và cảnh báo `tier_disabled`. Client lưu `enabledTiers` vào state; offline dùng bundled `A` và hiện ghi chú. | Tắt B không ảnh hưởng A; crafted `p` có knob B vẫn bị ép default; `gen_params_schema.py --check` không phụ thuộc env |
| A3.4 | Instrumentation | Log A/B toggle, knob được dùng, profile lưu, render/cache hit, prefetch fail. Không log nội dung nhạy cảm. | Có dashboard/query đủ để chạy gate §7.5 |
| A3.5 | Test | A/B theo bar/beat khi `tempo` đổi; B chưa ready; prefetch/pin; LiveRoom disabled; `appliesTo`; tier; URL. | `test:musicalize` + backend pass |

**Ghi chú A/B**: “score-aware” không có nghĩa là hai player chạy song song vô hạn. Nó nghĩa là B phải có đủ dữ liệu để chart/DFI/MusicXML khớp với tiếng. Nếu B chỉ khác mix (color/noise), đường audio-only vẫn dùng chung cơ chế; không cần hai implementation.

### Wave 2 — B0: nền schema v3

| ID | Hạng mục | Việc chính |
|---|---|---|
| B0.1 | Kiểu field | `ParamField` thêm `kind: number/choice/toggle`, `choices`, `auto`, `appliesTo`, `tier`; `default` giữ kiểu tương ứng. Khai báo trước toàn bộ key B/C và 3 knob guitar. |
| B0.2 | Canonical mixed type | Number dùng `pythonNumber`/`json.dumps`; choice là JSON string có quote; toggle là `true/false`. `normalizeParams` validate/clamp theo kind. Thêm **test vector hash xuyên ngôn ngữ** cho number/string/bool. |
| B0.3 | Migration | Backend `decode_params` nhận schema 2 và 3; client `decodeParams` nhận 2 và 3. Link writer vẫn ghi schema 2 trong giai đoạn chuyển tiếp; chỉ đổi sang 3 khi app floor hỗ trợ. Profile store migrate **theo schema chính xác**: chỉ `schema === 1` mới nhân `noise` legacy; `schema === 2` giữ nguyên. |
| B0.4 | Generator/fixture | `gen_params_schema.py` sinh type mới và fixture với **đủ tier** (`schema_payload(enabled=True, tiers=ALL_TIERS)`); runtime endpoint overlay env. Test `--check` trong môi trường có/không có env. |
| B0.5 | UI control | Thêm `ChoiceRow`, `ToggleRow`; tab mới tên **“Nâng cao”** (không dùng lại “Sâu hơn” của group `texture`); group collapse; a11y `adjustable`/`radio`/`switch`, keyboard, touch target. |
| B0.6 | Guitar voice | Tích hợp 3 knob từ PR #137 sau schema v3; giữ thứ tự balance **sau `humanize()`**, DFI **trước** balance; cập nhật comment “ten knobs” ở `params.ts`, `link.ts`, `client.ts`. |
| B0.7 | Test | `DEFAULT_HASH` mới một lần; schema `--check`; v2 link round-trip; profile v2 có `noise: 0.2` vẫn 0.2; hash vector number/string/bool; tier env. |

**Không đổi âm thanh Default ở B0.** Đây là pha bắt buộc trước mọi knob B/C.

### Wave 3 — B1: hòa âm & vùng âm

| ID | Hạng mục | Việc chính | AC |
|---|---|---|---|
| B1.1 | `harmony` | Lọc catalog và scale `SEVENTH_TENSION_COST` (trong `chords.py`) cùng borrowed bias (`chords.py`/`form.py`). `0` dùng **floor theo variant**: symphony/ambient/minimalist/guitar = triad, không borrowed; jazz = vẫn có 7th, không 9th/borrowed. `2` mở tối đa trong catalog của variant. | Default sequence identical; jazz 0 vẫn có 7th nhưng không 9th/borrowed; symphony 0 không có 4-note chord; `harmony=2` nhiều màu hơn trên corpus cố định |
| B1.2 | `register` | `shift = sign(x) * floor(abs(x) + 0.5)` với `x = (value - 1) * 3` semitone; 0 = −3, 1 = 0, 2 = +3. Dịch chromatic các bound, áp sau `register_for(key)` và trước `tune_register()`; guitar kẹp ±2 và chạy `assert_playable`, fallback shift 0 + warning nếu không playable. Không đổi `KEY_RING`. | Default 1.0 trả cùng object; 0/2 dịch đúng ±3 trên register gốc; ensemble hẹp có thể clamp, ghi nhận trong test; guitar playable; không đụng logic key của PR #34 |
| B1.3 | UI | Label “Tối giản / Chuẩn / Phong phú”, “Thấp / Chuẩn / Cao”; help text; hint jazz ở `harmony=0`; A/B. | Người dùng hiểu knob mà không cần đọc docs |
| B1.4 | Test | Default parity; vocabulary theo variant; register bounds; guitar playability; **pairwise** `harmony × motion` chuẩn bị cho C2. | Không regression ngoài profile mới |

### Wave 4 — C1: guitar technique

| ID | Hạng mục | Việc chính | AC |
|---|---|---|---|
| C1.1 | `technique` | Chỉ áp dụng `variant === "guitar"`; override `_dominant_pattern`/`_patterns` qua whitelist theo ensemble (`classic`, `villa`, `barrios`, `brouwer`, `bach`, `torroba`). | Không chọn pattern ngoài whitelist |
| C1.2 | Fallback | Nếu pattern được chọn không playable hoặc sai meter/BPM, fallback pattern auto + warning `technique_fallback`. | Không có tổ hợp nào raise `Unplayable` |
| C1.3 | `position` (optional) | Thế tay thấp/chuẩn/cao; chỉ làm nếu `technique` ổn định. | Không phá `_playable` |
| C1.4 | Test + span | Thêm `span` vào `render_guitar_score`/`_Ctx` **hoặc** test ở tầng `plan_*` (`plan_week`, `plan_month`, `plan_quarter`, `plan_year`) nơi span còn. Ma trận ensemble × character × span × technique; chạy `assert_playable`; pairwise `register × technique`. | Default 1.0 trả cùng score; mọi tổ hợp playable |

### Wave 5 — C2: Viterbi motion

| ID | Hạng mục | Việc chính | AC |
|---|---|---|---|
| C2.1 | `motion` | Scale đúng bốn hằng số trong `form.py`: `TRANSITION_WEIGHT`, `SECOND_BAR_STAY_COST`, `SINGLE_BAR_CHANGE_PENALTY`, `EXTENDED_STAY_PENALTY`. Không expose raw weight. | Default sequence identical |
| C2.2 | Test | Corpus cố định; `motion=0` ít đổi hơn 1.0; `motion=2` nhiều hơn; không sinh hợp âm ngoài catalog; pairwise `harmony × motion`. | Quan hệ đơn điệu, không slot lỗi |
| C2.3 | Audit | Nghe thử 5 variant ở 0/1/2; ghi nhận progression lạ. | Không có progression phá thể loại |

### Wave 6 — B2/B3: khung, tiết nhịp, discovery

| ID | Hạng mục | Phạm vi an toàn | Rủi ro |
|---|---|---|---|
| B2.1 | `frame` | auto / không khung / ngắn / dài, chỉ cho span dài `1M/3M/1Y`; 1D giữ `daily_frame` riêng. Chỉ đổi edge bars, không đổi body. | Trung bình |
| B2.2 | `meter` | Chỉ mở nơi đã có retarget: Torroba `retarget_torroba_meter`, guitar `_guitar_meter`. Jazz `swing_for` là playback swing, **không phải** meter. Chưa mở 4/4→3/4 toàn cục. | Cao |
| B2.3 | Discovery `form`/`key` | Chỉ viết spike/ADR, chưa code knob. `form` phải trả lời: là trục body structure hay chỉ là `span` + `frame`? `key` rebase trên PR #34, giữ bản sắc giọng. | Cao |
| B2.4 | Gate | Chỉ cam kết B2/B3 khi đạt gate §7.5. | — |

### Wave 7 — D: sau khi B/C ổn định

| ID | Hạng mục | Ghi chú |
|---|---|---|
| D1 | Profile server/auth | Chuyển profile local lên server, giữ schema/hash; quota và migration |
| D2 | AI sinh profile | AI chỉ trả JSON params; validate qua `/params/validate`; không nhận code/FFmpeg |
| D3 | DFI xuyên profile | So sánh corpus giữa các profile; hiện chỉ Default |
| D4 | Community preset | Chia sẻ/duyệt preset; có thể làm trước D1 nếu chỉ là file tĩnh |

---

## 6. Sprint đầu tiên

Wave 1 ước 2–3 tuần. Sprint đầu là **3 tuần** để bao hết A3.1–A3.5, không tách A3.4/A3.5 ra ngoài.

| Tuần | Ngày | Việc |
|---|---|---|
| 1 | 1–2 | Chốt state A/B; định nghĩa musical position (bar/beat/fraction); thiết kế prefetch/pin |
| 1 | 3–5 | A/B path audio + peaks; B chưa ready; không auto-save |
| 2 | 6–8 | A/B score-aware: MusicXML/DFI/chart; crossfade/gap; `ReplayRoom`; disable `LiveRoom` |
| 2 | 9–10 | `appliesTo` + `effectiveParams` + badge thay đổi ẩn |
| 3 | 11–12 | Tier flag + fixture all tiers + server enforcement |
| 3 | 13–14 | Instrumentation + test + docs/ADR |

Sau sprint này sẽ có dữ liệu thật để quyết định B1.

---

## 7. Test và tiêu chí nghiệm thu

### 7.1 Backend

- `test_params.py`: schema v3, default hash mới, normalize mixed type, `--check` không drift.
- `test_params_migration.py` (mới): decode `p` schema 2; profile store v2; hash của profile cũ đổi một lần, Default vẫn `""`.
- `test_params_hash_vectors.py` (mới): cùng params number/string/bool cho cùng hash ở Python và TS.
- `test_harmony.py` (mở rộng): `harmony=0/1/2`; default sequence identical; jazz floor; không có hợp âm ngoài catalog.
- `test_keys.py`/`test_params.py`: `register` cực trị; guitar playable.
- `test_sonify_guitar.py`: ma trận `technique`; `assert_playable`; pairwise `register × technique`.
- `test_dfi.py`: DFI key có `params_hash` cho mọi knob mới; Default/legacy giữ tuple cũ.
- `test_params_cache.py`: `cache_mark()` đúng; prune/LRU không xoá bản mới; pin A/B.
- Pairwise: `harmony × motion`, `tempo × register`, `dynamics × humanize` (đã có).

### 7.2 Frontend

- `params.test.ts`: normalize/encode/decode mixed type; default hash; migration; hash vector.
- `link.test.ts`: `p` schema 2 vẫn mở; schema 2 có field B/C bị client cũ bỏ qua; `writeLink` ghi schema 2 trong transition; `p` xuất hiện ở audio và peaks.
- `profileStorage` test: profile v1 nhân noise đúng; profile v2 có `noise: 0.2` giữ 0.2.
- `TuningPanel`: **tách logic thuần** (visible fields, changedCount, effectiveParams) để test bằng `tsx`; repo chưa có React test renderer, không thêm dependency chỉ để test panel. Nếu cần component test, thêm `@testing-library/react-native` như một quyết định riêng.
- A/B: musical position, B chưa ready, prefetch/pin, LiveRoom disabled.
- A11y: `ChoiceRow`/`ToggleRow`/A/B toggle có role, label, keyboard, touch target.

### 7.3 Nghe thử

Không nghe toàn bộ 100+ tổ hợp. Sampling plan:

- Mỗi knob số: nghe **0 / 1 / 2** trên 5 variant, một ensemble đại diện mỗi variant = 15 lượt/knob.
- `register`/`harmony`: thêm 1.5 để kiểm tra phi tuyến = 5 lượt/knob.
- Guitar: chỉ `technique` cần đủ 6 ensemble × 0/2 = 12 lượt; `register` guitar chỉ 3 ensemble đại diện.
- Chia reviewer nếu có; ghi nhận “đạt/không đạt” thay vì nghe lại toàn bộ.

### 7.4 Definition of done

- Default parity: score/MusicXML byte-identical; audio Default không đổi tên file.
- Schema `--check` xanh; `DEFAULT_HASH` pin đúng một lần.
- Link `p` cũ và mới round-trip; profile cũ migrate; `noise` không bị nhân đôi.
- Không có cache collision; prune/LRU bounded; A/B pin hoạt động.
- Guitar không raise `Unplayable` ở mọi tổ hợp knob.
- A/B không auto-save; `LiveRoom` không hiện A/B.
- Docs cập nhật; có ghi chú rollback bằng tier flag.

### 7.5 Gate cho Wave 6

Đề xuất threshold, chỉnh sau khi có dữ liệu:

- A/B được dùng trong ≥20% phiên nghe lại, hai tuần liên tiếp.
- ≥10% profile đã lưu có ít nhất một knob B/C.
- Có ≥5 yêu cầu/feedback cụ thể về đổi cấu trúc bài hoặc giọng.
- Không có regression DFI/cache quá 1% sau B1/C1/C2.

Nếu không đạt, dừng ở Wave 5.

---

## 8. Rủi ro và cách giảm

| Rủi ro | Cách giảm |
|---|---|
| Default lệch tiếng | Snapshot score/MusicXML; test parity; tier flag; không bump revision nếu không cần |
| Guitar vỡ thế tay | `assert_playable` làm cổng; fallback auto + warning; test ma trận |
| Schema v3 làm hỏng link cũ | Link writer ghi schema 2 trong transition; server/client đọc 2+3; test client cũ; banner fallback nếu cần |
| Profile v2 bị nhân `noise` lần nữa | Migration key theo `schema === 1`, không `< current`; test `noise: 0.2` |
| Canonical string/bool lệch Python–TS | Test vector hash xuyên ngôn ngữ cho cả 3 kind |
| Tier flag làm `--check` phụ thuộc env | Fixture luôn đủ tier; runtime overlay env; test cả hai môi trường |
| Bật/tắt tier làm hash đổi | Chấp nhận; chỉ xảy ra lúc rollout, ghi log và để LRU dọn cache cũ; không đổi tier trong lúc render |
| `appliesTo` làm hash phụ thuộc variant | Hash context-free; chỉ effective params khi render; chấp nhận cache trùng |
| A/B prefetch bị LRU xoá | Pin hai hash trong phiên; hiện trạng thái “đang chuẩn bị B” |
| A/B prefetch làm tăng tải render | Chỉ prefetch khi người dùng mở A/B; debounce; dùng slot MuseScore hiện có; hiện trạng thái chờ |
| A/B làm mất vị trí khi `tempo` đổi | Giữ bar/beat/fraction, không giữ giây; test tempo 0.75/1.25 |
| Form/meter làm lệch chart/DFI | Chỉ mở nơi đã có retarget; test `frame_seconds`, duration, DFI trace |
| UI quá tải | Group collapse, tab “Nâng cao”, chỉ hiện field áp dụng, A/B thay vì bắt nghe lại |
| Cache phình | LRU hiện có; có thể giảm `VSTOCK_PARAMS_CACHE_MAX` cho B/C |
| ContextVar rò rỉ | Giữ pattern `compose_params` hiện tại; test async/thread |
| Trùng việc với PR #34 | `register` chỉ dịch biên độ; `key` rebase trên plan giọng gốc; không tự tạo `KEY_RING` thứ hai |

---

## 9. Quyết định còn mở

Đã chốt ở §0: A/B scope, B draft, link schema 2, `appliesTo` client/server, bỏ `form`/`key` khỏi bảng chốt, gộp guitar voice vào v3, format tier.

Còn mở:

1. **Profile dùng chung hay theo variant?** V1 dùng chung và giữ saved values. Nếu UX thấy khó hiểu, có thể thêm badge “knob này chỉ áp dụng cho guitar” thay vì tách store.
2. **`form` là trục mới hay chỉ là `span` + `frame`?** Cần spike/ADR trước khi thành knob. Nếu chỉ là span/frame, không thêm key `form`.
3. **`key` có cần thành knob không?** Nếu có, rebase PR #34; nếu không, giữ `stock_home_key` và chỉ dùng `register` để đổi vùng.
4. **A/B crossfade hay gap?** Doc chốt crossfade 120 ms; nếu platform không ổn định, fallback gap ≤150 ms. Cần test trên web/native trước khi khóa AC.
5. **Có cần chia sẻ B qua URL không?** V1 chỉ chia sẻ A. Nếu cần, thêm `b=` hoặc `pb=` sau, không trộn vào `p`.

---

## 10. Việc không làm trong đợt này

- Không expose raw trọng số Viterbi, chuỗi FFmpeg, biểu thức, đường dẫn file.
- Không cho nhập số bar/section tùy ý trước khi có resample và audit DFI.
- Không đổi bản sắc giọng mặc định của từng mã nếu chưa có quyết định sản phẩm.
- Không làm editor từng nốt, mixer đa stem, hay realtime đổi knob khi đang phát.
- Không làm auth/server profile trước khi A/B và B1 ổn định.
