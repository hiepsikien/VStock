# Tầng B/C của parameter profile — Lộ trình và hạng mục triển khai

> **Trạng thái**: kế hoạch v9 — đã implement một phần ở [PR #139](https://github.com/hiepsikien/VStock/pull/139); các giới hạn ghi ở §11.
>
> **Đọc cùng**: [`sonify-params-profile-plan.md`](./sonify-params-profile-plan.md), [`musicalize-plan.md`](./musicalize-plan.md), [`sonify-humanize-preset-plan.md`](./sonify-humanize-preset-plan.md), [PR #137 — volume ba bè guitar](https://github.com/hiepsikien/VStock/pull/137), [PR #34 — giọng gốc và chuyển giọng](https://github.com/hiepsikien/VStock/pull/34), [PR #139 — implementation](https://github.com/hiepsikien/VStock/pull/139).
>
> **Mục tiêu**: mở rộng bàn tinh chỉnh từ tầng A (7 knob, 10 sau PR #137) sang các knob tầng B (hòa âm, vùng âm, khung) và tầng C (kỹ thuật guitar, nhịp đổi hợp âm), mà vẫn giữ `Default` bất biến, cache/DFI nhất quán, và không biến phòng nghe thành DAW.

---

## 0. Quyết định đã chốt

Tám điểm dưới đây chốt hướng triển khai. Các mục còn mở nằm ở §9.

| # | Quyết định |
|---|---|
| 1 | **A/B chỉ làm ở `ReplayRoom`**, và là **DFI-aware**: so sánh audio, peaks, movement metadata và DFI. Với `1D` dùng `RecapManifest` (audio/peaks/dfi); với `1W/1M/3M/1Y` dùng `SpanManifest.movements[].dfi`. Không có endpoint MusicXML/score diff, nên A/B không so sánh score chart. Chart giá là dữ liệu chung, không prefetch riêng. A/B bắt đầu từ `savedParams`; nếu savedParams đổi trong lúc mở A/B thì reset A/B. `LiveRoom` không có playhead để giữ; A/B ở live là việc sau, hành vi là restart stream. |
| 2 | **B là draft, không auto-save.** Preview B không gọi `planPlayParams`, không tạo profile. `Lưu` lưu không phát; `Play` khi đang ở B thì lưu draft, phát B và kết thúc A/B (B trở thành A mới). |
| 3 | **Link `p` tiếp tục ghi schema 2 trong giai đoạn chuyển tiếp.** Tách `LINK_SCHEMA_VERSION` khỏi `SCHEMA_VERSION`; `encodeParams` nhận schema; `/validate` nhận 2+3. Toàn bộ `p` (link, audio, peaks) dùng cùng schema 2 trong transition. App cũ đọc schema 2, giữ knob A và bỏ qua field B/C lạ. |
| 4 | **`p` do server quyết định tier.** Client gửi **`savedParams`**, server `applyTiers` rồi mới hash/cache/DFI. Client `paramsKey(savedParams)` chỉ là session/UI key, không phải cache hash. `appliesTo` chỉ tạo `renderParams`. Hash không phụ thuộc variant/ensemble/span. Không xoá giá trị đã lưu khi đổi variant. |
| 5 | **Bỏ `form` và `key` khỏi bảng knob chốt.** `form` để discovery sau A/B; `key` chờ PR #34 và quyết định sản phẩm về bản sắc giọng. |
| 6 | **Merge PR #137 (guitar voice) trước B0**, chấp nhận `DEFAULT_HASH` đổi hai lần: một lần khi #137 vào `main`, một lần khi B0 lên schema v3. B0 chuyển 3 knob guitar đã merge sang schema v3. |
| 7 | **Tier flag tách khỏi fixture.** Fixture committed luôn chứa đủ tier; endpoint runtime mới overlay env. `VSTOCK_SONIFY_PARAMS_TIER` dạng `A`, `A,B`, `A,B,C`; mặc định `A`; token lạ bị bỏ qua kèm log. |
| 8 | **Telemetry MVP có endpoint batch tối thiểu.** Client gửi batch `play`/`ab_toggle`/`profile_save`/`knob_change`/`prefetch_fail`; server lưu JSONL/SQLite, không PII. `play` mang `sessionId`, `span`, `variant`, `ensemble`; `profile_save` mang `schema`, `enabledTiers`, số knob B/C. Mỗi event có `eventId` để retry không đếm trùng. Endpoint cap batch 100, payload 64 KB; rate limit ở proxy. Server logs giữ render/cache/DFI. Gate §7.5 tính trên dữ liệu tổng hợp này. Nếu deploy nhiều instance, JSONL/SQLite local phải gom về một store trước khi tính gate. |

**Hệ quả của #6**: PR #137 body hiện đã mô tả code/test (không còn docs-only); trước khi merge chỉ cần xác nhận lại mô tả và hash. B0.6 chuyển `apply_voice_balance` + test sang schema v3. Hai lần đổi hash chấp nhận được vì chỉ ảnh hưởng cache non-default/DFI, LRU dọn file cũ.

---

## 1. Hiện trạng

### 1.1 Tầng A đã có

> Baseline đối chiếu là `9734a87`: 7 field, `DEFAULT_HASH = 5800e09635be`. Tại PR #137 head `0f366a1`: 10 field, 3 guitar knob là signed velocity offset −12…+12, `DEFAULT_HASH = 8653a4d3fcad`. Sau B0: schema 3, hash mới. Nếu #137 còn đổi range/hash, cập nhật lại mốc này.

| Thành phần | Trạng thái |
|---|---|
| Schema | Tại base `9734a87`: `SCHEMA_VERSION = 2`, 7 field `number`. Sau PR #137: 10 field, vẫn schema 2 |
| Canonical hash | `params_key()` / `params_hash()`; hash pin đổi theo từng mốc: `5800e09635be` → `8653a4d3fcad` (#137) → hash B0 |
| Cache | `cache_mark()` trả `""` cho Default, `_nh/_nc/_nh_nc` cho legacy, `_p<hash>` cho profile khác |
| Context | `compose_params()` ContextVar, đã dùng trong `audio.py` và `services/dfi.py` |
| DFI | `_recap_key` / `_movement_key` có `params_hash` cho bản `_p<hash>`; `dfiParamsHash` là field riêng |
| API | `/sonify/params/schema`, `/validate`, `/presets`; generator `scripts/gen_params_schema.py` |
| UI | `TuningPanel.tsx` render group/field động; profile local; URL `p=`; legacy `h/c` |
| Preset | Default, Gần, Ấm, Sống, Dày |

### 1.2 Khoảng trống cho tầng B/C

Các điểm dưới đây đối chiếu tại base `9734a87`. Nếu PR #137 đã merge, mục 2 (`changedCount`) có thể đã được sửa một phần; các mục còn lại vẫn đúng.

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
- **Schema v3 là cửa một lần cho B/C.** PR #137 ship trước trên schema 2, nên `DEFAULT_HASH` đổi hai lần: một lần ở #137, một lần ở B0. Chấp nhận vì #137 đã có code/test và chỉ ảnh hưởng cache non-default/DFI.
- **Form/meter chạm nhiều bất biến.** Chúng đổi độ dài bài, số bar, `frame_seconds`, mapping giá, guitar pattern, DFI trace. Đây là việc có thể làm, nhưng phải tách khỏi B1 và có test riêng.

---

## 2. Nguyên tắc thiết kế

1. **Default parity tuyệt đối.** Mọi knob mới ở default phải cho score/MusicXML **byte-identical** với hiện tại. Audio Default chỉ đổi khi có revision có chủ ý.
2. **Macro knob, không expose raw weight.** Không đưa `TRANSITION_WEIGHT`, `SEVENTH_TENSION_COST`, chuỗi FFmpeg hay trọng số Viterbi lên UI. Chỉ đưa các trục người nghe hiểu: “Màu hòa âm”, “Vùng âm”, “Kỹ thuật”, “Nhịp hòa âm”.
3. **`tier` khác `appliesTo`.**
   - `tier` là rollout toàn cục. Server ép field ngoài tier về default **trước khi hash** để audio/cache nhất quán; hash vì vậy phụ thuộc cấu hình tier. Client chỉ dùng `enabledTiers` để ẩn/hiện UI.
   - `appliesTo` là ngữ cảnh âm nhạc (variant/ensemble/span). Server tạo `renderParams`; client có bản local cho UI; server cảnh báo; **không** ép default và **không** đưa context vào hash.
4. **Không xoá giá trị đã lưu.** Đổi variant chỉ đổi cách hiển thị/render, không xoá field khỏi profile. Profile dùng chung vẫn giữ nguyên dữ liệu.
5. **Một lần bump schema v3.** Khai báo trước toàn bộ key B/C, kể cả key còn tắt sau tier flag. PR #137 ship trước trên v2, nên hash đổi hai lần: #137 và B0.
6. **A/B trước khi mở B/C.** A/B so sánh audio, peaks, movement metadata và DFI; không cần MusicXML/score diff.
7. **Rollout theo tầng.** Server trả `enabledTiers`; client ẩn group ngoài tầng được bật. Default vẫn là `A`.
8. **Không thay đổi bản sắc dữ liệu nếu chưa có chủ ý.** `key` và form là thay đổi bản sắc bài; chỉ làm sau khi có quyết định sản phẩm rõ ràng.
9. **Playability là cổng, không phải gợi ý.** Mọi knob guitar phải đi qua `assert_playable`; nếu không playable thì fallback auto + warning, không render bản vỡ.

### 2.1 Parameter flow

Một bảng duy nhất để tránh lệch giữa profile, `p`, hash, cache, DFI và A/B:

| Object | Dùng cho |
|---|---|
| `savedParams` | Profile storage, `changedCount`, nguồn UI, **`p` gửi lên server**. Không bị xoá khi đổi variant |
| `tierParams = applyTiers(savedParams)` | **Server-side**: `params_hash`, `cache_mark`, DFI key, render base. Client có thể tính bản local để hiển thị theo `enabledTiers`, nhưng không dùng để lọc `p` |
| `renderParams = applyAppliesTo(tierParams, context)` | **Server-side**: audio/peaks/DFI/score render. Client dùng bản local cho UI effective |
| `aParams` / `heardParams` | Snapshot A; URL khi đang A/B |
| `bParams` | Draft B; chỉ dùng cho preview, không ghi profile/URL |
| `playingParams` | Side đang phát (`A` hoặc `B`) cho player và DFI đang nghe |
| `paramsKey` / `tierHash` | `paramsKey(savedParams)` là session/UI key; `tierHash` là hash server trả sau `applyTiers` trong `RecapManifest.paramsHash` / `SpanManifest.paramsHash` (và `SpanManifest.movements[].paramsHash`), dùng pin/cache |

Quy tắc:

- **Server-authoritative `p`**: client gửi `savedParams`; server `applyTiers` rồi mới hash/cache/DFI. Client offline hoặc cache tier cũ không làm mất giá trị B đã lưu.
- `paramsKey` của client chỉ là canonical string cho React key và A/B session key; **không** dùng làm cache hash. Hash audio do server tính sau `applyTiers`; A/B pin dùng `tierHash` server trả cho **cả A và B**.
- `appliesTo` chỉ tạo `renderParams`; server cảnh báo `inapplicable` nhưng không sửa `p`/hash.
- Preview B không ghi `heardParams`, không đổi URL, không ghi profile. `Lưu` lưu `bParams`; `Play` khi ở B lưu draft, phát B, gán `aParams = bParams`, `activeSide = A`, rồi kết thúc A/B.

---

## 3. Bản đồ knob đề xuất

### 3.1 Guitar voice — PR #137 trước B0

PR #137 hiện dùng **signed velocity offset**, không phải hệ số nhân. Default `0` trả nguyên score.

| Key | Nhãn | Kiểu | Khoảng | Default | Phạm vi | Ghi chú |
|---|---|---|---:|---:|---|---|
| `guitar_high` | Bè cao | number, signed | −12…+12, step 1 | 0 | guitar | Cộng offset vào velocity bè cao; `0` là bản hiện tại |
| `guitar_mid` | Bè trung | number, signed | −12…+12, step 1 | 0 | guitar | Cộng offset vào velocity voice 2 và 4 |
| `guitar_bass` | Bè bass | number, signed | −12…+12, step 1 | 0 | guitar | Cộng offset vào velocity ngón cái; áp sau `humanize()`, trước MusicXML; DFI tính trước balance |

### 3.2 Tầng B/C — knob mới

| Key | Nhãn | Kiểu | Giá trị | Default | Phạm vi | Wave | Ý nghĩa |
|---|---|---|---|---|---|---|---|
| `harmony` | Màu hòa âm | number | 0.00–2.00, step .05 | 1.00 | tất cả | B1 | 0 = tối giản trong vocabulary của variant; 1 = hiện tại; 2 = nhiều màu hơn |
| `register` | Vùng âm | number | 0.00–2.00, step .05 | 1.00 | tất cả; guitar giới hạn | B1 | 0 = thấp/ấm; 1 = hiện tại; 2 = cao/sáng. Dịch bounds, không đổi giọng |
| `technique` | Kỹ thuật | number | 0.00–2.00, step .05 | 1.00 | guitar: Bach/Torroba | C1 | 0 = dễ/arpeggio/chorale; 1 = hiện tại; 2 = điêu luyện/tremolo/dance. Các ensemble khác ẩn knob vì baseline chưa playable dưới profile hiện tại |
| `motion` | Nhịp hòa âm | number | 0.00–2.00, step .05 | 1.00 | tất cả | C2 | 0 = giữ hợp âm lâu; 1 = hiện tại; 2 = đổi hợp âm dồn dập |
| `frame` | Khung | choice | auto / không khung / ngắn / dài | auto | span dài `1M/3M/1Y` | B2 | Độ dài warm-up/cool-down; 1D giữ `daily_frame` riêng |
| `meter` | Tiết nhịp | choice | auto / 4/4 / 3/4 / 6/8 / 12/8 | auto | chỉ Torroba | B2 | Hiện chỉ áp dụng cho guitar/Torroba; jazz swing là playback flag, không phải meter. Các ensemble khác ẩn knob |

**Không đưa vào bảng chốt**: `key` và `form`. Hai trục này nằm ở §9 và chỉ thành knob sau khi có quyết định/discovery tương ứng.

**Không đưa vào đợt này**: raw Viterbi weights, chuỗi FFmpeg, số bar tùy ý, editor từng nốt, realtime đổi knob khi đang phát.

---

## 4. Lộ trình theo wave

| Wave | Pha | Nội dung | Kết quả | Ước lượng | Rủi ro |
|---|---|---|---|---|---|
| **0** | #137 | Merge guitar voice trên schema 2; xác nhận body/test; pin hash mới | Guitar có 3 knob balance; hash đổi lần 1 | 0.5 tuần | Thấp |
| **1** | A3 | A/B DFI-aware, `appliesTo`, tier flag, telemetry | So sánh được A/B; UI không hiện knob sai thể loại; có số liệu để quyết định B2 | 2–3 tuần | Trung bình |
| **2** | B0 | Schema v3, migration, UI choice/toggle, generator, migrate guitar voice | Nền cho mọi knob B/C; hash đổi lần 2; Default không đổi audio | 2–3 tuần | Trung bình |
| **3** | B1 | `harmony`, `register` | 2 macro knob tạo khác biệt rõ về hòa âm và vùng | 3–4 tuần | Trung bình |
| **4** | C1 | `technique`, guard playability | Guitar có “độ điêu luyện” mà vẫn chơi được | 2–3 tuần | Trung bình |
| **5** | C2 | `motion` | Điều khiển nhịp đổi hợp âm | 2 tuần | Trung bình |
| **6** | B2/B3 | `frame`, `meter` hẹp, discovery `key`/`form` | Cấu trúc bài sâu hơn, nếu có nhu cầu | 3–6 tuần | Cao |
| **7** | D | Profile server/auth, AI sinh profile, DFI xuyên profile | Cá nhân hóa và vận hành | 4–6 tuần | Cao |

Ước lượng B1 + C1 + C2 = **7–9 tuần**. Có thể dừng sau Wave 3 hoặc 4. Wave 6 chỉ nên làm sau khi các gate ở §7.5 đạt.

---

## 5. Hạng mục triển khai

### Wave 1 — A3: A/B DFI-aware + nền vận hành

| ID | Hạng mục | Việc chính | AC |
|---|---|---|---|
| A3.1 | A/B DFI-aware | Chỉ `ReplayRoom`. A = `aParams`/`heardParams`; B = `bParams` draft. So sánh **audio, peaks, movement metadata và DFI**: `1D` dùng `RecapManifest` (audio/peaks/dfi); `1W/1M/3M/1Y` dùng `SpanManifest.movements[].dfi`. Không có MusicXML/score diff. Chart giá là dữ liệu chung, không prefetch riêng. Lazy prefetch: chỉ chuẩn bị B khi người dùng mở A/B; debounce và cancel khi draft đổi; prefetch movement hiện tại của B, không chỉ movement 0. Giữ **vị trí nhạc** (bar/beat/fraction), không phải giây. Crossfade 120 ms là **AC tạm**, chốt sau test web/native; fallback gap ≤150 ms và không click. Pin **cả hai phía**: `paramsKey(savedParams)` + `tierHash(A)` và `paramsKey(bParams)` + `tierHash(B)` trong phiên để prune/LRU không xoá. `LiveRoom` disable A/B. URL chia sẻ A, không chia sẻ B. | State machine rõ `aParams`/`bParams`/`activeSide`/`playingParams`; B preview **không** ghi `heardParams`, không đổi URL/profile; `Lưu` chỉ lưu; `Play` khi ở B lưu draft, phát B, gán A = B rồi kết thúc A/B; B chưa ready thì hiện “Đang chuẩn bị B”; toggle không lệch nhạc; không click; chạy được cả `1D` và span dài |
| A3.2 | `appliesTo` + parameter flow | Thêm `appliesTo`/`tier` dưới dạng **metadata v2-compatible** (không đổi `p`/hash) trong A3; B0 mới thêm `kind/choices/signed`. Client gửi `savedParams`; server `applyTiers` rồi hash; client dùng `enabledTiers` để ẩn/hiện UI và `renderParams()` local cho hiển thị; `p` vẫn gửi saved params. **Giữ saved values.** `TuningPanel` lọc group; `changedCount()` chỉ đếm field hiện; profile có badge “có thay đổi ẩn”. Server `/validate` nhận context và cảnh báo `inapplicable`; render hiện chưa cắt field khỏi score, chỉ cảnh báo. | Đổi variant không xoá profile; nghe Giao hưởng không thấy knob guitar; hash không đổi chỉ vì variant; `p` gửi `savedParams`, server hash sau `applyTiers`; client `paramsKey` chỉ session key; offline tier A không làm mất giá trị B đã lưu |
| A3.3 | Tier flag | `enabledTiers` trong schema runtime; env `VSTOCK_SONIFY_PARAMS_TIER` dạng `A`, `A,B`, `A,B,C`, mặc định `A`; token lạ bỏ qua + log. Fixture committed luôn đủ tier. Server ép key ngoài tier về default trước hash và cảnh báo `tier_disabled`. Client lưu `enabledTiers` vào state; offline dùng bundled `A` và hiện ghi chú. | Tắt B không ảnh hưởng A; test tier bằng **field synthetic** ở A3; crafted `p` có field B/C thật được test ở B0.7; `gen_params_schema.py --check` không phụ thuộc env |
| A3.4 | Telemetry MVP | **Server structured logs** cho render/cache/DFI (`paramsHash`, variant, cache hit, render ms, DFI). **Endpoint batch tối thiểu** `POST /v1/sonify/events` nhận `play`, `ab_toggle`, `profile_save`, `knob_change`, `prefetch_fail`; `play` mang `sessionId`/`span`/`variant`/`ensemble`; `profile_save` mang `schema`/`enabledTiers`/số knob B/C. Mỗi event có `eventId`; client buffer local khi offline rồi flush; lưu JSONL/SQLite, không PII. Cap batch 100, payload 64 KB; rate limit ở proxy. `prefetch_fail` là event client, không phải server log. Nếu chạy nhiều instance, cần gom JSONL/SQLite về một store. | Có log/query đủ để tính denominator §7.5: phiên `ReplayRoom` có ít nhất một lần `play`; số profile lưu có knob B/C sau rollout; số lần A/B; cache hit; prefetch fail |
| A3.5 | Test | A/B state machine; `1D` `RecapManifest` + span `SpanManifest`; musical position khi `tempo` đổi; lazy prefetch/debounce/cancel; B chưa ready; pin cả A và B; LiveRoom disabled; `appliesTo`; tier synthetic; URL; link `p` schema 2; event batch có `play`/`eventId`. | `test:musicalize` + backend pass |

**Ghi chú A/B**: “DFI-aware” không có nghĩa là hai player chạy song song vô hạn. Nó nghĩa là B phải có đủ audio/peaks/metadata/DFI để tai và chỉ số khớp nhau. Nếu B chỉ khác mix (color/noise), đường audio-only vẫn dùng chung cơ chế; không cần hai implementation.

### Wave 2 — B0: nền schema v3

| ID | Hạng mục | Việc chính |
|---|---|---|
| B0.1 | Kiểu field | A3 đã thêm `appliesTo`/`tier` dạng metadata; B0 thêm `kind: number/choice/toggle`, `choices`, `auto`, `signed`, `default` giữ kiểu tương ứng. `signed` giữ semantics offset có dấu của guitar voice, không suy ra từ step. Khai báo trước toàn bộ key B/C. |
| B0.2 | Canonical mixed type | Number dùng `pythonNumber`/`json.dumps`; number có `signed` vẫn là JSON number (có thể âm), không phải string; choice là JSON string có quote; toggle là `true/false`. `normalizeParams` validate/clamp theo kind và `signed`. Choice values phải ASCII; nếu không, dùng `ensure_ascii=False` ở cả Python và TS. Thêm **test vector hash xuyên ngôn ngữ** cho number/string/bool, gồm số âm. |
| B0.3 | Migration | Backend `decode_params` nhận schema 2 và 3; client `decodeParams` nhận 2 và 3. Tách `LINK_SCHEMA_VERSION = 2` khỏi `SCHEMA_VERSION`; `encodeParams(params, schema)`; `/validate` nhận 2+3. Toàn bộ `p` (link/audio/peaks) dùng schema 2 trong transition; chỉ đổi sang 3 khi app floor hỗ trợ. Profile store migrate **theo schema chính xác**: chỉ `schema === 1` mới nhân `noise` legacy; `schema === 2` giữ nguyên. |
| B0.4 | Generator/fixture | `gen_params_schema.py` sinh type mới và fixture với **đủ tier** (`schema_payload(enabled=True, tiers=ALL_TIERS)`); runtime endpoint overlay env. Test `--check` trong môi trường có/không có env. |
| B0.5 | UI control | Thêm `ChoiceRow`, `ToggleRow`; tab mới tên **“Nâng cao”** (không dùng lại “Sâu hơn” của group `texture`); group collapse; a11y `adjustable`/`radio`/`switch`, keyboard, touch target. |
| B0.6 | Guitar voice migration | Sau khi #137 merge, chuyển 3 knob guitar **signed velocity offset** sang schema v3; giữ `signed=True`, range −12…+12, step 1, default 0; giữ thứ tự balance **sau `humanize()`**, DFI **trước** balance; giữ test `test_voice_balance.py`; cập nhật comment “ten knobs” ở `params.ts`, `link.ts`, `client.ts`. |
| B0.7 | Test | `DEFAULT_HASH` đổi lần hai (B0), sau lần một ở #137; test cả hai mốc; schema `--check`; v2 link round-trip; profile v2 có `noise: 0.2` vẫn 0.2; hash vector number/string/bool; tier env; crafted `p` có field B/C thật bị ép default. |

**Không đổi âm thanh Default ở B0.** Đây là pha bắt buộc trước mọi knob B/C.

### Wave 3 — B1: hòa âm & vùng âm

| ID | Hạng mục | Việc chính | AC |
|---|---|---|---|
| B1.1 | `harmony` | Lọc catalog và scale `SEVENTH_TENSION_COST` (trong `chords.py`) cùng borrowed bias (`chords.py`/`form.py`). `0` dùng **floor theo variant**: symphony/ambient/minimalist/guitar = triad, không borrowed; jazz = vẫn có 7th, không 9th/borrowed. `2` mở tối đa trong catalog của variant. | Default sequence identical; jazz 0 vẫn có 7th nhưng không 9th/borrowed; symphony 0 không có 4-note chord; `harmony=2` nhiều màu hơn trên corpus cố định |
| B1.2 | `register` | `shift = sign(x) * floor(abs(x) + 0.5)` với `x = (value - 1) * 3` semitone; 0 = −3, 1 = 0, 2 = +3. Dịch chromatic các bound, áp sau `register_for(key)` và trước `tune_register()`; guitar kẹp ±2 và chạy `assert_playable`, fallback shift 0 + warning nếu không playable. Không đổi `KEY_RING`. | Default 1.0 trả cùng object; non-guitar 0/2 dịch ±3 trên register gốc, guitar ±2; ensemble hẹp có thể clamp, ghi nhận trong test; guitar playable; không đụng logic key của PR #34 |
| B1.3 | UI | Label “Tối giản / Chuẩn / Phong phú”, “Thấp / Chuẩn / Cao”; help text; hint jazz ở `harmony=0`; A/B. | Người dùng hiểu knob mà không cần đọc docs |
| B1.4 | Test | Default parity; vocabulary theo variant; register bounds; guitar playability; **pairwise** `harmony × motion` chuẩn bị cho C2. | Không regression ngoài profile mới |

### Wave 4 — C1: guitar technique

| ID | Hạng mục | Việc chính | AC |
|---|---|---|---|
| C1.1 | `technique` | Chỉ áp dụng `variant === "guitar"`; override `_dominant_pattern`/`_patterns` qua whitelist theo ensemble (`classic`, `villa`, `barrios`, `brouwer`, `bach`, `torroba`). | Không chọn pattern ngoài whitelist |
| C1.2 | Fallback | Nếu pattern được chọn không playable hoặc sai meter/BPM, fallback pattern auto + log `technique_fallback`. Warning API/UI để sau. | Không có tổ hợp nào raise `Unplayable` khi baseline playable; baseline vốn không playable thì giữ baseline an toàn |
| C1.3 | `position` (optional) | Thế tay thấp/chuẩn/cao; chỉ làm nếu `technique` ổn định. | Không phá `_playable` |
| C1.4 | Test + span | Thêm `span` vào `render_guitar_score`/`_Ctx` **hoặc** test ở tầng `plan_week`/`plan_month`/`plan_quarter`/`year_specs` (chưa có `plan_year`) nơi span còn. Ma trận ensemble × character × span × technique; chạy `assert_playable`; pairwise `register × technique`. | Default 1.0 trả cùng score; mọi tổ hợp playable |

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

PR #137 merge trước sprint (Wave 0). Wave 1 ước 2–3 tuần. Sprint đầu là **3 tuần** để bao hết A3.1–A3.5.

| Tuần | Ngày | Việc |
|---|---|---|
| 1 | 1–2 | Chốt state machine A/B (`aParams`/`bParams`/`activeSide`/`playingParams`); musical position; thiết kế lazy prefetch/pin |
| 1 | 3–5 | A/B path audio + peaks + `RecapManifest` (1D) / `SpanManifest` (dài); B chưa ready; không auto-save; `Lưu`/`Play` behavior |
| 2 | 6–8 | A/B DFI-aware: DFI comparison; crossfade/gap; `ReplayRoom`; disable `LiveRoom` |
| 2 | 9–10 | `appliesTo` + server-authoritative `savedParams → applyTiers → renderParams` + badge thay đổi ẩn |
| 3 | 11–12 | Tier flag + fixture all tiers + server enforcement + synthetic tier test |
| 3 | 13–14 | Telemetry endpoint batch + server logs + test + docs/ADR |

Sau sprint này sẽ có dữ liệu thật để quyết định B1.

---

## 7. Test và tiêu chí nghiệm thu

### 7.1 Backend

- `test_params.py`: schema v3, default hash mới, normalize mixed type, `--check` không drift.
- `test_params_migration.py` (mới): decode `p` schema 2; profile store v2; hash của profile cũ đổi **hai mốc** (#137 rồi B0), Default vẫn `""`.
- `test_params_flow.py` (mới): `savedParams` → server `applyTiers` → `renderParams`; `p` chứa saved (kể cả B khi tier tắt); server hash sau `applyTiers`; client `paramsKey` chỉ session key; `appliesTo` không đổi hash; offline tier A không mất giá trị B.
- `test_params_hash_vectors.py` (mới): đọc **cùng file vector JSON** (ví dụ `backend/tests/fixtures/params_hash_vectors.json`) cho number/string/bool/số âm; `params.test.ts` hoặc script Node đọc cùng file; CI chạy cả Python và TS/Node.
- `test_events.py` (mới): endpoint batch nhận event, validate schema, lưu JSONL/SQLite, không nhận PII; `play`/`eventId`; cap batch 100/payload 64 KB; batch rỗng/hỏng trả lỗi rõ.
- `test_harmony.py` (mở rộng): `harmony=0/1/2`; default sequence identical; jazz floor; không có hợp âm ngoài catalog.
- `test_keys.py`/`test_params.py`: `register` cực trị; guitar playable.
- `test_sonify_guitar.py`: ma trận `technique`; `assert_playable`; pairwise `register × technique`.
- `test_voice_balance.py`: signed offset −12/0/+12, không clip, default 0 trả nguyên score; chỉ guitar.
- `test_dfi.py`: DFI key có `params_hash` cho mọi knob mới; Default/legacy giữ tuple cũ.
- `test_params_cache.py`: `cache_mark()` đúng; prune/LRU không xoá bản mới; pin A/B.
- Pairwise: `harmony × motion`, `tempo × register`, `dynamics × humanize` (đã có).

### 7.2 Frontend

- `params.test.ts`: normalize/encode/decode mixed type; default hash; migration; đọc cùng file `params_hash_vectors.json`; `paramsKey(savedParams)` là session key, không phải server hash.
- `link.test.ts`: `p` schema 2 vẫn mở; schema 2 có field B/C bị client cũ bỏ qua; `writeLink` dùng `LINK_SCHEMA_VERSION = 2`; `p` trên audio/peaks cũng schema 2; `/validate` nhận 2+3.
- `profileStorage` test: profile v1 nhân noise đúng; profile v2 có `noise: 0.2` giữ 0.2.
- `TuningPanel`: **tách logic thuần** (visible fields, changedCount, `renderParams`, badge) để test bằng `tsx`; repo chưa có React test renderer, không thêm dependency chỉ để test panel. Nếu cần component test, thêm `@testing-library/react-native` như một quyết định riêng.
- A/B: state machine (`aParams`/`bParams`/`activeSide`/`playingParams`); B preview không ghi heard/URL; `Lưu` vs `Play`; `1D` `RecapManifest` + span `SpanManifest`; musical position; lazy prefetch/debounce/cancel; pin **cả A và B** (`paramsKey` + `tierHash` mỗi phía); LiveRoom disabled.
- Telemetry: client buffer local khi offline, flush batch, không gửi PII; event names khớp endpoint.
- A11y: `ChoiceRow`/`ToggleRow`/A/B toggle có role, label, keyboard, touch target.

### 7.3 Nghe thử

Không nghe toàn bộ 100+ tổ hợp. Sampling plan:

- Mỗi knob số: nghe **0 / 1 / 2** trên 5 variant, một ensemble đại diện mỗi variant = 15 lượt/knob.
- Guitar voice: nghe **−12 / 0 / +12** trên `classic` và một ensemble còn lại; kiểm tra offset không clip.
- `register`/`harmony`: thêm 1.5 để kiểm tra phi tuyến = 5 lượt/knob.
- Guitar: chỉ `technique` cần đủ 6 ensemble × 0/2 = 12 lượt; `register` guitar chỉ 3 ensemble đại diện.
- Chia reviewer nếu có; ghi nhận “đạt/không đạt” thay vì nghe lại toàn bộ.

### 7.4 Definition of done

- Default parity: score/MusicXML byte-identical; audio Default không đổi tên file.
- Schema `--check` xanh; `DEFAULT_HASH` pin đúng theo từng mốc: #137 (`8653a4d3fcad` tại head `0f366a1`) và B0 (hash mới).
- Link `p` cũ và mới round-trip; profile cũ migrate; `noise` không bị nhân đôi.
- Không có cache collision; prune/LRU bounded; A/B pin hoạt động cho **cả A và B**.
- Guitar không raise `Unplayable` ở mọi tổ hợp knob.
- A/B không auto-save; `LiveRoom` không hiện A/B; A/B chạy cả `1D` và span dài.
- Event batch endpoint hoạt động; gate §7.5 tính được denominator.
- Docs cập nhật; có ghi chú rollback bằng tier flag.

### 7.5 Gate cho Wave 6

Đề xuất threshold, chỉnh sau khi có dữ liệu. Nguồn: endpoint batch event + server structured logs.

- **Denominator**: phiên `ReplayRoom` có ít nhất một lần Play, tính theo ngày/tuần; không tính `LiveRoom`.
- A/B được dùng trong ≥20% phiên `ReplayRoom`, hai tuần liên tiếp.
- ≥10% profile **được lưu sau khi B1/C1/C2 bật** có ít nhất một knob B/C; không tính profile cũ trước rollout.
- Có ≥5 yêu cầu/feedback cụ thể về đổi cấu trúc bài hoặc giọng; nguồn là issue/support, ghi ngày và nội dung.
- Không có regression DFI/cache quá 1% sau B1/C1/C2; đo bằng log `paramsHash`, cache hit/miss, render ms.
- Nếu thiếu dữ liệu hoặc denominator <30 phiên/tuần, gate chuyển **qualitative**: review thủ công + quyết định sản phẩm.

Nếu không đạt, dừng ở Wave 5.

---

## 8. Rủi ro và cách giảm

| Rủi ro | Cách giảm |
|---|---|
| Default lệch tiếng | Snapshot score/MusicXML; test parity; tier flag; không bump revision nếu không cần |
| Guitar vỡ thế tay | `assert_playable` làm cổng; fallback auto + warning; test ma trận |
| Schema v3 làm hỏng link cũ | `LINK_SCHEMA_VERSION = 2`; `encodeParams(params, schema)`; server/client đọc 2+3; test client cũ; banner fallback nếu cần |
| PR #137 + B0 đổi hash hai lần | Chấp nhận; chỉ cache non-default/DFI bị re-render; ghi log mốc hash và để LRU dọn |
| Profile v2 bị nhân `noise` lần nữa | Migration key theo `schema === 1`, không `< current`; test `noise: 0.2` |
| Canonical string/bool lệch Python–TS | Test vector hash xuyên ngôn ngữ cho cả 3 kind; choice ASCII hoặc `ensure_ascii=False` |
| Tier flag làm `--check` phụ thuộc env | Fixture luôn đủ tier; runtime overlay env; test cả hai môi trường |
| Bật/tắt tier làm hash đổi | Chấp nhận; chỉ xảy ra lúc rollout, ghi log và để LRU dọn cache cũ; không đổi tier trong lúc render |
| `appliesTo` làm hash phụ thuộc variant | Client gửi `savedParams`; server `applyTiers` rồi hash; `appliesTo` chỉ tạo `renderParams`; chấp nhận cache trùng |
| Parameter flow lệch giữa profile/p/hash/DFI | Bảng §2.1 là hợp đồng; server-authoritative `p`; test `savedParams → applyTiers → renderParams`; server là nguồn hash cuối |
| A/B prefetch bị LRU xoá | Pin **cả A và B**: `paramsKey` + `tierHash` mỗi phía; hiện trạng thái “đang chuẩn bị B” |
| A/B bỏ sót `1D` | Test cả `RecapManifest` (1D) và `SpanManifest.movements[].dfi`; không chỉ test span dài |
| A/B prefetch làm tăng tải render | Lazy: chỉ prefetch khi mở A/B; debounce/cancel; dùng slot MuseScore hiện có; hiện trạng thái chờ |
| A/B làm mất vị trí khi `tempo` đổi | Giữ bar/beat/fraction, không giữ giây; test tempo 0.75/1.25 |
| Telemetry không có hạ tầng | Endpoint batch tối thiểu + buffer local; lưu JSONL/SQLite; `play` event cho denominator; nhiều instance phải gom store; gate có fallback qualitative |
| Form/meter làm lệch chart/DFI | Chỉ mở nơi đã có retarget; test `frame_seconds`, duration, DFI trace |
| UI quá tải | Group collapse, tab “Nâng cao”, chỉ hiện field áp dụng, A/B thay vì bắt nghe lại |
| Cache phình | LRU hiện có; có thể giảm `VSTOCK_PARAMS_CACHE_MAX` cho B/C |
| ContextVar rò rỉ | Giữ pattern `compose_params` hiện tại; test async/thread |
| Trùng việc với PR #34 | `register` chỉ dịch biên độ; `key` rebase trên plan giọng gốc; không tự tạo `KEY_RING` thứ hai |

---

## 9. Quyết định còn mở

Đã chốt ở §0: A/B scope + payload (`RecapManifest`/`SpanManifest`), B draft/Play behavior, link schema 2, **server-authoritative `p`/tier**, `appliesTo` chỉ render, bỏ `form`/`key` khỏi bảng chốt, merge PR #137 trước B0, format tier, **telemetry endpoint batch**.

Còn mở:

1. **Profile dùng chung hay theo variant?** V1 dùng chung và giữ saved values. Nếu UX thấy khó hiểu, có thể thêm badge “knob này chỉ áp dụng cho guitar” thay vì tách store.
2. **`form` là trục mới hay chỉ là `span` + `frame`?** Cần spike/ADR trước khi thành knob. Nếu chỉ là span/frame, không thêm key `form`.
3. **`key` có cần thành knob không?** Nếu có, rebase PR #34; nếu không, giữ `stock_home_key` và chỉ dùng `register` để đổi vùng.
4. **A/B crossfade hay gap?** AC tạm là crossfade 120 ms; fallback gap ≤150 ms nếu platform không ổn định. Chốt sau test web/native.
5. **Có cần chia sẻ B qua URL không?** V1 chỉ chia sẻ A. Nếu cần, thêm `b=` hoặc `pb=` sau, không trộn vào `p`.

---

## 10. Việc không làm trong đợt này

- Không expose raw trọng số Viterbi, chuỗi FFmpeg, biểu thức, đường dẫn file.
- Không cho nhập số bar/section tùy ý trước khi có resample và audit DFI.
- Không đổi bản sắc giọng mặc định của từng mã nếu chưa có quyết định sản phẩm.
- Không làm editor từng nốt, mixer đa stem, hay realtime đổi knob khi đang phát.
- Không làm auth/server profile trước khi A/B và B1 ổn định.

---

## 11. Ghi chú implementation hiện tại

Các điểm dưới đây là giới hạn có chủ ý của bản đang chạy, không phải AC mới:

- `renderParams()` trong client là **helper local cho hiển thị/effective params**, chưa được dùng trong pipeline audio/peaks/DFI. `p` vẫn gửi `savedParams`; server là nguồn hash cuối.
- Warning `inapplicable` hiện chỉ có ở `/validate`; client chưa gọi endpoint này và chưa hiển thị warning. UI chỉ ẩn field theo `appliesTo`.
- `POST /v1/sonify/params/pin` và `POST /v1/sonify/events` chưa có auth/rate limit trong code; dựa vào proxy. `_pins`/`_SEEN_EVENT_IDS` là memory từng process; multi-instance cần store chung.
- `technique` chỉ hiện cho Bach/Torroba; các ensemble còn lại baseline chưa playable dưới profile hiện tại nên knob bị ẩn thay vì no-op.
- `technique_fallback` hiện là `logger.warning`, chưa thành warning API/UI.
- `assert_playable` trong wrapper dùng score C-space, nên `C_KEY` là đúng; nếu sau này score giữ key đã transpose thì phải truyền `key` tương ứng.
- `apply_tiers` backend hiện là helper/test seam; production đi qua `normalize_with_warnings`.
