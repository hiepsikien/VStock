# Kế hoạch: Federico Moreno Torroba (`ensemble = "torroba"`)

> **Trạng thái**: nền tảng (dialect, 4 pattern cơ sở, La♭ trên Sol, Picardy) đã hát trên `main`. Mở rộng câu, vòng quay đầu và 4 kiểu kết cấu *Sonatina* tổ hợp câu nằm ở [`docs/sonify-guitar-torroba-phrase-plan.md`](./sonify-guitar-torroba-phrase-plan.md).
> **Nguồn phác thảo**: [`docs/torroba.txt`](./torroba.txt).
> **Khung đang chạy**: [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md). Một nhà là một dialect hòa âm cộng một palette pattern. Thân bài khóa một pattern theo mood. Bè cao là đường giá, đọc bằng `_melody_at`.

Torroba là nhà thứ sáu của guitar nylon. Chất của ông là vòng Andalucia và giai điệu hát trên dây buông. Bè cao giữ nguyên đường giá. Pattern và nốt lấy đà chỉ đổi cách phát nốt đó.

---

## 1. Chỗ của ông trong bộ sáu nhà

| Nhà | Chỗ đang giữ |
|---|---|
| Bach | Đối vị, vòng quãng 5 |
| Sor | Hợp âm ba cổ điển, song thanh quãng 3/6 (`cantabile`) |
| Barrios | Lãng mạn Nam Mỹ, tremolo, chuông |
| Villa-Lobos | Màu ấn tượng Brazil: sus2, add9, trượt song song, hợp âm khối |
| Brouwer | Hiện đại, nghịch, ostinato |
| **Torroba** | Tây Ban Nha: vòng i–VII–VI–V, bậc V là hợp âm trưởng, giai điệu được hát nốt nằm sát trên gốc của bậc V |

Villa đã giữ màu ấn tượng (hợp âm treo, trượt song song). Torroba giữ địa lý còn thiếu: Phrygian / Andalucia. Giọng thứ của engine là Đô thứ, nên vòng của ông trong code là **Cm → Bb → Ab → G → Cm**. Nốt màu là **La♭ ngân trên Sol trưởng**.

Tempo ngày: **96 BPM**, cùng vùng với Bach. Điệu vũ lấy nhịp nhún từ meter và cách ngân, không từ một BPM ngày cao hơn. Các span khác giữ BPM của span (`1W` 90, chương 4/4 của `1M` / `3M` / `1Y` trong khoảng 96–108).

---

## 2. Bè cao là giá

`_place_melody` trong `guitar.py` đưa chuỗi close vào cửa sổ đàn. Pattern đọc từng móc bằng `_melody_at` (`guitar_patterns.py`). Phách yếu giữ nốt thang. Phách mạnh bị `quantize_strong_beats` kéo về nốt hợp âm nếu lệch không quá một bậc thang.

Mỗi ô của Torroba vẫn cất đúng cao độ `_melody_at`. Nốt lấy đà, slur, bóng quãng 3/6 và harmonics là cách phát nốt ấy.

### La♭ trên Sol trưởng

Viterbi (`plan_markov_chords` trong `form.py`) chạy trước lượng tử hóa, trên cao độ thô. `G` là `{7, 11, 2}`, `G7` là `{7, 11, 2, 5}`. La♭ là pitch class 8, không nằm trong hai hợp âm đó. `bar_quantization_loss` phạt `STRONG_BEAT_WEIGHT = 2.5` mỗi phách mạnh và `HELD_STRONG_WEIGHT = 1.0` mỗi móc giữ cùng nốt. Nốt La♭ giữ từ ô `Ab` sang ô `G` còn bị `_breaks_held_note_across_barline` cộng `CROSS_BAR_BREAK_PENALTY = 1.2`.

Nhánh `G` / `G7` sẵn có trong loss chỉ nâng Si♭ (pitch class 10) thành Si qua `sing_leading`. La♭ không đi qua nhánh đó.

`color_credit` không phải cửa sửa. Mức credit hiện có là `0.70`, và credit bị xóa khi đổi hợp âm trừ khi `is_parent`. Một phách mạnh đã tốn 2.5. Hợp âm có loss 0 khi phách mạnh là La♭ là hợp âm chứa pitch class 8: `Ab`, `Abmaj7`, `Fm`, `Fm7`. `Cm` là `{0, 3, 7}`, không chứa La♭.

Cách làm, chỉ khi `dialect.name == "torroba"` và giọng thứ:

- Trong loss, `G` và `G7` nghe thêm pitch class 8. Bước lượng tử của nốt La♭ trên hai hợp âm đó là 0. Các nốt khác vẫn bị phạt như cũ.
- `_breaks_held_note_across_barline` không coi một La♭ giữ qua vạch ô là gãy khi hợp âm mới là `G` hoặc `G7`.

`quantize_strong_beats` chạy hai lần. Cả hai lần đều phải giữ La♭, nếu không lần trước đã xóa nốt trước khi lần sau nhìn thấy:

1. `render.py`, trên `raw_pitches`, sau khi hợp âm đã chốt. Giữ La♭ khi cao độ thô là pitch class 8 và hợp âm ô đó là `G` hoặc `G7`.
2. `guitar.py` `_place_melody`, sau `_choose_shifts` và `_compress_monotone`. Hàm nhận `ensemble`. Ngay trước snap, nếu nốt trong `placed` vẫn là pitch class 8 thì giữ. Nén bậc có thể đổi pitch class để vừa cửa sổ. Không lấy `raw_pitches` viết đè lên nốt đã nén.

`quantize_strong_beats` còn một nhánh chung trước vòng từng hợp âm (`phrasing.py`). Run giữ qua nhiều ô lấy giao pitch class của các hợp âm ở phách mạnh. La♭ giữ qua `Cm → G` có giao `{7}`. Sol cách La♭ một bậc thang, nên cả run bị kéo về Sol trước khi tới vòng từng ô. Cửa `pc == 10` trên `G` / `G7` đang chặn cảm âm dẫn. Thêm cùng kiểu: ensemble là `torroba`, `run.midi % 12 == 8`, và một ô phách mạnh là `G` hoặc `G7` thì không đi nhánh giao đó. Hàm nhận `ensemble` với mặc định rỗng, để lời gọi từ jazz và Villa giữ nguyên. Cộng `{8}` vào pitch class của `G` không đủ: giao với `Cm` vẫn là `{7}`.

Ensemble khác vẫn nâng cảm âm dẫn trên át như hiện tại. Không ép La♭ nếu giá đang ở nốt khác.

### Ba bè

- **Cao**: đường giá. Phách mạnh là `_melody_at`. Liền bậc thì slur, gán trong renderer của pattern (mục 6). Nhảy thì một nốt lấy đà, mục 5.
- **Trung**: nốt hợp âm còn lại. Khi đường giá đi liền bậc (`|Δ| ≤ 2`), được hát bóng quãng 3 hoặc quãng 6 ngay dưới nốt giá, và bóng đó là nốt thang hoặc nốt hợp âm. Giá nhảy thì bóng tắt. Bóng không phải một đường giá thứ hai. `assert_playable` từ chối bè trung có cao độ vang trên 65, trừ `high_block` (bè cao từ 80), `thumb_cantabile`, etude của Villa và preludio. Bốn pattern dùng chung profile `"torroba"`. Cửa đó là `profile == "torroba"` và nốt trung vẫn dưới nốt cao nhất của bè cao, cùng dạng cửa `barrios_preludio`. Hợp âm ba tiếng của `danza` và `fandanguillo` cần cửa này khi giá nằm ở 72–79: bè trung trong thế tay năm phím rơi vào 66–69, và `high_block` chưa mở vì bè cao chưa tới 80.
- **Trầm**: một nốt pedal thuộc hợp âm. Trần bè trầm trong `assert_playable` là cao độ vang `40–53` (voice 3 trên 53 bị từ chối, trừ `thumb_cantabile` tới 64). Dây buông vang là `_OPENS = (40, 45, 50, 55, 59, 64)`. Sol buông là 55, nằm ngoài trần bass. Sol ở 43 là phím 3 dây 6, không phải dây buông. Pedal ưu tiên nốt hợp âm mà `written + semitones` rơi vào `{40, 45, 50}`, tức `_is_open` đã có trong `guitar_frame.py`. Ở Đô thứ không dịch giọng, bậc I là pitch class 0 và không trùng dây nào trong tập đó. Hợp âm Sol có dây buông hợp lệ là Rê (50), quãng năm, không phải gốc Sol. Bậc không có dây buông hợp lệ thì lấy nốt hợp âm thấp nhất trong vùng bass.

`Bar.ma20` chỉ được đọc ở `render.py` để phân `uptrend` / `downtrend` / `sideway`. `_Ctx` không có `ma20`. Pedal đọc `ChordSlot.regime`, truyền theo từng ô vào `_Ctx`. `uptrend` ưu tiên bậc I nếu hợp âm chứa nó. `downtrend` ưu tiên bậc V. `sideway`, hoặc lần gọi `render_guitar_score` không có regime, chỉ chọn nốt hợp âm có dây buông hợp lệ, không nghiêng I/V.

Vận tốc viết nằm trong band nylon hiện có: giai điệu `_MELODY` 64 đến `_MELODY_APEX` 72, bè trong `_INNER` 56, sàn đệm 40 (`guitar.py`). Không mở trần viết riêng. Humanize là mục 3.

---

## 3. Đăng ký

`torroba` đi cùng các chỗ `brouwer` và `bach` đã đứng:

- `src/api/client.ts`: `RecapEnsemble`, và `ENSEMBLE_ROWS.guitar` thêm `{ id: 'torroba', label: 'Torroba' }` sau Brouwer.
- `src/sonify/program.ts`: `GUITAR_BPM.torroba = 96`. Tên pattern mới thêm vào `PATTERN_NAMES`.
- `backend/app/sonify/guitar.py`: `GUITAR_BPM["torroba"] = 96`. Đây là bảng tempo ngày của backend. Bản TypeScript không thay nó.
- `backend/app/sonify/model.py`: `Ensemble` và `ENSEMBLES`.
- `backend/app/sonify/ensemble.py`: `_ROWS[("guitar", "torroba")] = (_NYLON,)` và `_ALLOWED["guitar"]`.
- `backend/app/schemas.py`: hai `Literal` ensemble (recap và span).
- `backend/app/sonify/harmony.py`: đăng ký `TorrobaDialect` trong `DIALECTS`. Guitar `classic` vẫn là Sor.
- `backend/app/sonify/program.py`: `_PATTERN_TITLE` cho bốn pattern ở mục 5.
- `backend/app/sonify/guitar_patterns.py`: bốn pattern vào `_FAMILY`. `_PROFILE` của cả bốn là `"torroba"`, để một cửa trần 65 phủ hết. Bốn dict fallback thêm `"torroba": "sonatina"`. Hôm nay ensemble lạ rơi về `"preludio"`. Bốn chỗ là cuối `_select_body`, cuối `_owning_pattern`, cuối `_fallback_body_pattern`, và đầu `headline_id`. Bốn dict đó không đủ. Tempo ngày là 96, còn `BARRIOS_TREMOLO_MIN_BPM` là 90. Trong `_select_body`, nhánh `ctx.bpm >= BARRIOS_TREMOLO_MIN_BPM and first_body` trả `"preludio"` trước khi tới dict cuối. `_dominant_pattern` và `_contrast_pattern` không có dict cuối: sau villa, chúng đi vào luật Barrios. Ba nhánh `ctx.ensemble == "torroba"` đứng cùng chỗ Bach và Brouwer, trước cửa BPM đó. Bảng mood của ba nhánh là mục 7.
- `backend/app/sonify/guitar_wave.py`: bốn khóa `("torroba", pattern)` trong `PROFILES`, và nhánh `_is_target` ở mục 5. Thiếu khóa thì `profile_for` trả `None` và sóng động lực bị phẳng. `backend/tests/test_guitar_wave.py` so `set(PROFILES)` với `_EXPECTED`. Bốn khóa mới phải có trong tập đó.
- `backend/app/sonify/guitar_scale_passages.py`: xem mục 6.
- `backend/app/sonify/humanize.py`: `_clamp_guitar` để `torroba` cùng nhóm trần 73 với `bach` và `classic`. Hàm này chạy trong `audio.py`, sau `apply_guitar_wave`. Nốt nó đọc đã là vận tốc sau sóng. Nốt còn từ 64 trở xuống giữ từ 64 trở xuống. Nốt đã được snap lên trên 64 thì vào 69–73. Nhóm còn lại mở tới 79.

Nhãn trên nút là tên nhà, **Torroba**.

---

## 4. `TorrobaDialect`

`MINOR_CATALOG` là `Cm`, `Cm7`, `Fm`, `Fm7`, `Dm7b5`, `G`, `G7`, `Ab`, `Abmaj7`, `Eb`, `Ebmaj7`, `F#dim7`. `Bb` (`BF`) và `Bb7` nằm trong `BORROWED`, không nằm trong catalog thứ. `extra("minor")` trả về `(BF,)`. Không thêm `BF7`. Vòng Andalucia dùng hợp âm ba Si♭. `G7` đã có sẵn trong catalog.

`root_step` của Si♭ là `"B"`. Hàng đó không có trong `_ROOT_TRANSITIONS` và không có trong `_MINOR_ROOT_BIAS`. Hợp âm nằm trong `extra()` đi qua `extra_floor`, nên `minor_bias` không bị gọi trên gốc B. `transition()` của mọi cặp giọng thứ có chạm `Bb` mà không nằm trong bảng Andalucia trả về `0.0`. Trả `None` thì `minor_root_probability` cũng ra 0 và cạnh bị bỏ. Bảng riêng là cách cạnh `Cm → Bb` và `Bb → Ab` thực sự được chọn.

Không thêm loại hợp âm sáu. Quãng sáu của ông là bóng bè trung ở mục 2. `extra()` không trả hợp âm treo, sus2, add9.

**Cấm**, theo kiểu `_SOR_MINOR_BANNED` / `_SOR_MAJOR_BANNED`:

| Mode | `allowed()` từ chối |
|---|---|
| Thứ | `Cm7`, `Fm7`, `Ebmaj7`, `Abmaj7`, `Dm7b5`, `F#dim7` |
| Trưởng | `Cmaj7`, `Fmaj7`, `Am7`, `Dm7`, `Em7`, `Ab`, `Eb`, `Bb7`, `Gm`, `Bm7b5` |

Giọng thứ còn được đứng: `Cm`, `Bb`, `Ab`, `G`, `G7`, `Fm`, `Eb`. Giọng trưởng còn được đứng: `C`, `F`, `G`, `G7`, `Bb`, `Fm`, cùng các hợp âm ba thuận thang `Am`, `Dm`, `Em` khi chúng đi ngang. `Bb` và `Fm` là màu mượn của giọng trưởng. Danh sách cấm của Sor có hai hợp âm này. Danh sách của Torroba không cấm chúng.

**Giọng thứ.** Vòng nhận diện, cạnh riêng cao hơn bước gốc thường:

`Cm → Bb → Ab → G → Cm`

`G → Cm` là cadenza, cạnh mạnh nhất. `G` trong vòng này là hợp âm trưởng. `G7` được đứng khi câu đang đổ vào cadenza. `Fm` và `Eb` chỉ là màu đi qua, không thay vòng.

`bias`: `selloff` kéo về nhánh xuống `Bb → Ab → G`. `rally` vẫn đi vòng đó.

**Picardy.** `allowed()` không biết ô hiện tại có phải ô cuối câu đóng (`phrase.closes`) hay không. `C` không có trong `MINOR_CATALOG`. Đưa `C` vào `extra("minor")` thì Viterbi dùng được nó giữa câu.

- Outro và cooldown: `_bell_chord(ctx, bar, velocity, picardy=True)` trong `guitar_frame.py`, cùng cửa Barrios, Brouwer và Bach đã có. Ô pedal vẫn khóa bậc I của mode.
- Thân bài: hậu kiểm nằm trong `render_guitar_score`, ngay sau `_place_melody` và trước `render_patterned_voices`. `render_guitar_score` tự dựng `chord_at` từ `slots`, rồi `_place_melody` gọi `quantize_strong_beats` lần hai. Đổi `Cm` thành `C` trên `slots` trước bước đó thì lần hai thấy `C` (`{0, 4, 7}`) và lượng tử hóa lại ô. Đặt sau `_place_melody` thì cả hai lần snap đã xong, melody là cao độ cuối, và unit test gọi thẳng `render_guitar_score` cũng nhận Picardy. Ô cuối câu đóng (`phrase.closes`), hợp âm đang là `Cm`, melody đã đặt của ô đó không có pitch class 3: đổi chord trên `slots`, dựng lại `chord_at` cho phần đệm, và dựng lại `harmonies` trước khi ghi `Score`. `render.py` tạo `harmonies` từ slots cũ rồi truyền vào. Không gọi `quantize_strong_beats` thêm lần nào. Không đổi các ô khác của câu.

**Giọng trưởng.** Bè cao ở lại thang Đô trưởng. Màu Tây Ban Nha nằm ở `Bb` và `Fm`. Khung vẫn là `C`, `F`, `G`. Cạnh đáng có: `C → Bb`, `Bb → F`, `F → C`. Cặp giọng trưởng có chạm `Bb` hoặc `Fm` mà không nằm trong bảng này trả về `0.0`.

`allowed`: hợp âm của dialect này không đứng trên pedal intro/outro. Ô pedal giữ hợp âm bậc I của mode.

---

## 5. Bốn pattern

Mỗi pattern khóa cả một mood, cùng cách `_dominant_pattern` đang làm với Bach và Brouwer. Trong một pattern, mọi slot hát đều gọi `_melody_at`.

Guitar không có nhịp 3/8. `form.py` có `METER_44` (8 móc đơn, phách mạnh 0 và 4), `METER_34` (6 móc đơn, phách mạnh 0, móc 4 được cộng trọng số), và `METER_68` (6 móc đơn, phách mạnh 0 và 3). Một ô 6/8 là hai nhóm ba móc.

Hợp âm phách đầu của `fandanguillo` và `danza` có tối đa ba tiếng cùng vang: voice 3, voice 2, voice 1. `assert_playable` từ chối bốn tiếng. Chỉ `barrios_tremolo` và `barrios_preludio` được mở trần đó. Nốt trên cùng của khối là `_melody_at` của móc đó.

| Pattern | Nguồn | Tay phải | Mood | Bè cao |
|---|---|---|---|---|
| `castillo` | *Castillos de España*, *Sonatina* Andante | Rải thưa, bass buông, một nốt hát dài mỗi ô | `calm`. `selloff` khi BPM ≤ 72 | Đúng nốt giá, ngân cả ô |
| `sonatina` | *Sonatina* chương I và III | Rải móc đơn. Giai điệu ở phách mạnh. Bè trung đi các móc còn lại | `rally`. `selloff` ở 4/4 | Mỗi phách mạnh là `_melody_at`. Liền bậc thì slur trong renderer. Nhảy thì nốt lấy đà |
| `fandanguillo` | *Suite Castellana* I, *Piezas características* | Một hợp âm ở móc 0, giai điệu đáp ở các móc sau. Lưới theo meter bên dưới | `volatile`. Scherzo khi giá chạy | Nốt trên của hợp âm móc 0 là giá. Mỗi phách mạnh còn lại cũng là `_melody_at` |
| `danza` | *Suite Castellana* III | Hợp âm staccato đầu mỗi nhóm ba móc, rồi nốt đáp | Scherzo đi ngang, biên hẹp, `calm` | Mỗi hợp âm lấy nốt giá của móc đó làm tiếng trên. Nốt đáp tiếp đường giá, hoặc một nốt láng giềng quay về. Không bịa thêm một close |

Lưới `fandanguillo`:

- **4/4**: hợp âm ở móc 0. Giai điệu ở móc 2, 4 và 6. Móc 4 là phách mạnh thứ hai. Móc lẻ là bè trung hoặc nghỉ.
- **6/8**: hợp âm ở móc 0. Giai điệu ở móc 2 và 3. Móc 3 là phách mạnh thứ hai. Móc 1, 4, 5 là bè trung hoặc nghỉ.
- **3/4**: hợp âm ở móc 0. Giai điệu ở móc 2 và 4. Móc 4 là móc được cộng trọng số của meter.

Lưới `danza`:

- **6/8**: hai nhóm. Hợp âm staccato ở móc 0 và móc 3. Đáp ở móc 1–2 và 4–5.
- **3/4**: một hợp âm ở móc 0. Đáp ở móc 1–2. Móc 4 là nốt giai điệu, không phải hợp âm thứ hai.
- **4/4**: `danza` không đứng ở chương 4/4. `volatile` của 4/4 là `fandanguillo`.

`selloff` không có pattern bi ca. Sor đã có `elegiaque`. Cùng `sonatina`, vòng rơi xuống Sol trưởng và bè cao được phép hát La♭. Chương chậm thì `selloff` về `castillo`.

Rasgueado là hợp âm ba tiếng ở các móc hợp âm phía trên. Staccato là cách ngắt, không phải một bậc vận tốc riêng. Không có pattern id riêng.

### Vận tốc trong ô

Số trong bảng là vận tốc pattern viết ra, trước `_shape_dynamics` và trước `apply_guitar_wave`. Thứ tự giữ `lead > bass > inner` qua `_under_lead`. Sàn 40. Không nốt nào viết trên `_MELODY_APEX` (72).

Thứ tự sau đó:

1. Pattern ghi `64`, `68`, `72`.
2. `_shape_dynamics` cộng `extra = round(4 * swell)` (`0..+4`) cho câu có `phrase.rise > 0`. Mặc định mỗi móc một mức. `galop` lấy một mức cho cả ô (`anchor = event.bar * ctx.epb`) để giữ đường viền phách.
3. `apply_guitar_wave` dịch cả ô bằng `round(C) + (viết - 64)`, rồi kẹp ở `min(v_ceil, raw)` với `v_ceil <= 63` (`WARM_LIMIT`). Cửa sổ đã khóa rộng từ 27 nên tâm ô không quá `v_ceil - 8`. Viết `68` thành tâm `+4`, viết `64` thành tâm `+0`. Cả hai vẫn từ 63 trở xuống. Độ chênh `+4` còn. Lớp móng chưa mở.
4. `_apply_snaps` ghi đè một số attack đã chọn bằng `_snapped_velocity`, từ 66 tới `snap_wide`. Nốt không được chọn ở lại mức affine.
5. `humanize` đọc vận tốc sau sóng. Nốt từ 64 trở xuống giữ nguyên. Nốt snap trên 64 vào 69–73.

Viết `max(_note_velocity, 68)` cho phách mạnh của điệu vũ tạo độ nảy `+4` sau affine. Nó không tự đưa nốt vào lớp móng. Lớp móng chỉ có khi `PROFILES` có snap và `_is_target` chọn đúng attack. `alpha_price < 0.25` thì ngân sách snap bằng 0, trừ `elogio_pizz`. Phiên phẳng của Torroba nghe độ nảy, không nghe móng.

`castillo` không snap, cùng kiểu `cantabile` và `noviembre`: `snap_calm` và `snap_wide` là `None`, `per_phrase` 0, `per_sec` 0, target `"none"`. `accent=True` trên phách mạnh chỉ là dấu nhấn. Chỗ nghe mạnh hơn là bè trong nhỏ hơn.

`sonatina`, `fandanguillo` và `danza` có snap. `_is_target` trả về đúng khi `voice == "lead"` và `event.accent`. Không lấy mọi nốt đỉnh, vì nốt đáp ở đỉnh câu sẽ chiếm chỗ móng của phách mạnh.

| Pattern | `snap_calm` / `snap_wide` | Mỗi câu / mỗi đoạn | Nghe sau humanize |
|---|---|---|---|
| `castillo` | không snap | 0 / 0 | toàn ô ở lại từ 63 trở xuống |
| `sonatina` | 66 / 68 | 1 / 2 | nốt được chọn nghe ở 69. Trần snap 68 không còn dải bên trên 69 |
| `fandanguillo`, `danza` | 68 / 70 | 1 / 3 | nốt được chọn nghe ở 69 hoặc 70. Các phách mạnh không được chọn giữ độ nảy `+4` trong vùng ấm |

Mỗi câu chỉ một nốt móng, và cả đoạn không quá ngân sách. Test không đòi mọi phách mạnh đều vào 69–73.

`danza` và `fandanguillo` dùng chung anchor cả ô trong `_shape_dynamics`, cùng cửa của `galop`. Một `extra` cho mọi móc trong ô. Nếu để mỗi móc một mức, câu đang lên có thể cộng `+1` vào hợp âm đầu ô (`68 → 69`) và `+4` vào nốt đáp (`64 → 68`), rồi affine giữ đúng khoảng đã bị rút đó. Bass và bè trung của cùng ô nhận cùng một `extra`, nên khoảng cách ba bè không đổi.

| Việc | Vận tốc viết |
|---|---|
| Giai điệu phách mạnh của `sonatina` và `castillo` | `_note_velocity`: câu phẳng 64, đỉnh câu 72, câu lên theo swell 60 rồi 68 rồi 72 rồi 62. `accent=True` trên attack đó |
| Giai điệu phách mạnh, và nốt trên của hợp âm `danza` / `fandanguillo` | `max(_note_velocity, 68)`. Đỉnh câu vẫn 72 |
| Giai điệu phách yếu và nốt đáp | 64, không accent |
| Nốt lấy đà | `_INNER` (56), thấp hơn nốt giải |
| Ba đến năm nốt chạy | các nốt lấy đà viết từ 64 trở xuống. Nốt tới dùng `_note_velocity` của đỉnh |
| Bass ở móc hợp âm hoặc đầu ô | `_under_lead` theo band, thấp hơn giai điệu ít nhất 2 |
| Bass ở móc yếu, nếu có | thấp hơn bass phách mạnh 4, sàn 40 |
| Bè trung | `_under_lead`: thấp hơn bass ít nhất 2 và thấp hơn giai điệu ít nhất 4. Band `p` là 50, `mp` là 54, `mf` là 56, `f` là 60, rồi siết bởi khoảng cách trên |
| Harmonics | 48 |
| Ô thở | giai điệu giữ vận tốc của nốt đang ngân, không đánh lại. Bè trung còn lại ở band `p` |

Phách mạnh theo meter: 4/4 là móc 0 và 4. 6/8 là móc 0 và 3. 3/4 là móc 0. Móc 4 của 3/4 là nốt giai điệu phách yếu (64), không phải accent thứ hai. Móc lẻ của 4/4 và các móc đệm còn lại chỉ có bè trung hoặc bass, không có accent.

**Nốt lấy đà.** `NoteEvent` và `_add_note` không có cờ grace. Thẻ `<grace/>` có trường độ 0. Nếu hai nốt bè cao cùng một thời điểm, `assert_playable` báo `two notes in the high voice`. Không thêm cờ grace.

Nốt lấy đà là một móc kép (`duration_beats = 0.25`) ở móc kép cuối của phách ngay trước phách mạnh, voice 1, `slur_start`. Nốt giá ở phách mạnh là `slur_stop` và vẫn là một tiếng. Bè trung nghỉ đúng móc kép đó. Đây không phải mordent của Bach: `_mordent_events` thay cả phách mạnh bằng ba móc kép. Phách mạnh của Torroba giữ một nốt giá.

**Harmonics.** `musicxml.py` không có thẻ `<harmonic/>`. Soundfont phát cao độ đã viết. Kim cương là cách ngân của `_bells`: cùng cao độ giá, vận tốc viết 48, bè trung nghỉ. Chỉ khi cao độ vang của nốt đang ngân đã trùng một nút harmonic tự nhiên của dây buông, tức nằm trong `{52, 57, 62, 67, 71, 76, 79}`, và nốt dài từ hai phách đen. Không kéo giá sang nút gần nhất. Không trùng thì đó là nốt ngân thường.

Tên in trên chương trình (`_PATTERN_TITLE` và `PATTERN_NAMES`): `Castillo`, `Sonatina`, `Fandanguillo`, `Danza`.

---

## 6. Lớp phủ trên câu

Không phải pattern mới. Đặt sau khi pattern của câu đã khóa.

- **Ô thở.** Ô cuối cụm 4 ô: bè trung bỏ khoảng nửa số nốt. Bè cao vẫn ngân close của ô đó.
- **Harmonics.** Như mục 5. Đổi màu của đúng nốt giá.
- **Slur.** Renderer của `sonatina`, nốt lấy đà và nét chạy ngắn tự gán `slur_start` / `slur_stop`. Cuối `render_patterned_voices` vẫn gọi `_slur()` cho mọi ensemble. Hàm đó chỉ bỏ ô `preludio` có khung. Mọi ô mà pattern là của Torroba phải vào `skip_bars`, nếu không `_slur()` gán thêm một slur thứ hai lên slur đã viết. `_slur()` gốc vẫn chỉ hammer khoảng `_HAMMER_SHARE = 0.04`, bỏ câu đầu, và chỉ vào nốt nhấn. Cửa đó không đủ cho cặp liền bậc của `sonatina`.
- **Nét chạy ngắn.** 3–5 nốt slur đổ vào nốt đỉnh khi `phrase.rise >= MIN_RISE` hoặc câu phá đỉnh. Nốt đỉnh vẫn là giá. Nét này là ornament trong pattern, cùng kiểu `_swarm_line` của Brouwer, và không ghi vào `scale_eighths`. `clear_scale_slurs` xóa slur trên mọi móc thuộc `scale_eighths`. `detect_price_impulses` chỉ dành khoảng 30% thân bài cho scale chung. Nét Torroba không xin ngân sách đó.
- **Scale chung**, nếu impulse vẫn chạy trên thân: đăng ký pattern vào `guitar_scale_passages.py`. `castillo` và `sonatina` vào `_HAT_PATTERNS`, hàng `_NARROW_ROWS` cùng bậc `cantabile` `(4, 16, 76)`. `fandanguillo` và `danza` vào `_KINETIC_PATTERNS`, hàng cùng bậc `polca` `(4, 18, 76)`. `_pitch_classes` và `_composer_step` có nhánh `ctx.ensemble == "torroba"`. Nốt áp cuối được là La♭ khi hợp âm đích là Sol trưởng. `classic_scale_step` chỉ bước trên thang của mode. Việc nâng Si♭ thuộc `sing_leading` lúc lượng tử hóa. Ngoại lệ mục 2 giữ La♭ trên đường đó. Các móc scale chung vẫn bị `clear_scale_slurs` gảy thật.

---

## 7. Bộ chọn macro

Đi cùng bảng ở mục 3.0 của [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md). Bài có khung khóa một pattern cho cả thân khi không có `trio` / `bridge`. Có đoạn tương phản thì A–B–A: A là `_dominant_pattern`, B là `_contrast_pattern`.

Hàng 4/4 áp cho mọi chương 4/4, không riêng `1D`: `1D` (96 BPM của Torroba), `1W` (90), `1M` I và IV (96), `3M` I (96), `3M` III (108), tháng mở `1Y` (100), tháng 12 của `1Y` (96).

| Khung | A | B |
|---|---|---|
| Mọi chương 4/4, 90–108 BPM | `calm` → `castillo`. `rally` → `sonatina`. `volatile` → `fandanguillo`. `selloff` → `sonatina` | Không có `trio` / `bridge` trên `1D` và `1W`. Chương có đoạn giữa thì theo hàng chậm hoặc scherzo của span đó |
| Chương chậm 3/4, 60–72 BPM | `castillo` | `bridge` → `sonatina` |
| Scherzo 6/8 | `calm` → `danza`. `rally` / `volatile` → `fandanguillo`. `selloff` → `castillo` | `trio` → `castillo` khi A là điệu. A đã là `castillo` thì B là `sonatina` |

Fixture không khung (`_framed(ctx) == False`) đi `_select_body`. Torroba dùng cùng bảng mood theo từng câu: `calm` là `castillo`, `rally` và `selloff` là `sonatina`, `volatile` là `fandanguillo`, chương chậm là `castillo` với `bridge` là `sonatina`. Không có vân tay riêng kiểu Barrios `1D`. Nhánh `torroba` trong `_select_body` đứng trước `ctx.bpm >= BARRIOS_TREMOLO_MIN_BPM`. Nhánh trong `_dominant_pattern` và `_contrast_pattern` đứng trước `ctx.bpm < BARRIOS_TREMOLO_MIN_BPM`. Dict `"sonatina"` chỉ là lưới khi không còn câu để chọn.

Intro và outro đi qua `guitar_frame.py`, cùng kiểu khung 2 ô và 4 ô của các nhà kia:

- `calm` / `rally`: bass buông ngân trong vùng 40–53, một nốt hát là giá của ô. Harmonics chỉ khi trùng cao độ vang ở mục 5.
- `volatile` / `selloff`: một hợp âm ba tiếng ở móc 0, nốt trên cùng là giá, rồi vào pattern thân.
- Giọng thứ, ô outro: `_bell_chord(..., picardy=True)`.

---

## 8. Phần giữ từ bản phác thảo

Giữ vòng Andalucia, bass buông làm keo giữa các ô, Danza đối đáp, nốt lấy đà và slur bám vào nốt hát, ô cuối câu làm thưa đệm, và trần vận tốc nylon sẵn có.

Các ý sau dừng ở bản phác thảo, không vào engine:

- Vòng một ô hợp âm, hai ô scale, ba ô rải. *Sonatina* ở lì một kết cấu cả câu. Nét chạy ngắn là ornament của pattern. Đổi tay phải từng ô cũng trái khóa một pattern của thân bài.
- Một ô chỉ có harmonic, hoặc một ô scale thay hết đường giá. Ô đó mất tiếng close.
- Hợp âm khối liên tục và hợp âm trượt theo MA20. Villa đã giữ hai việc đó. Regime đã tính từ close so với MA20 chỉ chọn bậc của pedal, mục 2.
- Rasgueado thành pattern của cú volume. Một hợp âm ba tiếng trong điệu vũ là đủ.
- Form A–BCB–A mới. `bridge` và `trio` đang có sẵn.
- Viết lại let-ring, tách vận tốc ba bè, và wedge dàn dây. Guitar đã có ngân chồng và band vận tốc. Wedge violin thuộc ensemble khác.
- Thẻ `<grace/>` và thẻ `<harmonic/>`. Nốt lấy đà là móc kép có slur. Kim cương là cao độ giá ngân theo kiểu chuông.

---

## 9. Thứ tự làm

1. **Dialect và La♭.** `extra("minor") = (BF,)`, hai bảng cấm, cạnh Andalucia trả trọng số, cặp lạ chạm `Bb` trả `0.0`. Loss của `G` / `G7` nghe pitch class 8. Cross-bar không phạt La♭ giữ sang hai hợp âm đó. Cả hai lần `quantize_strong_beats` giữ La♭ khi nốt đang xét vẫn là pitch class 8, kể cả nhánh giao pitch class khi run giữ qua `Cm` và `G`. Picardy đứng sau `_place_melody` trong `render_guitar_score`. Pattern tạm vẫn là arpeggio thường. Test: giọng thứ đi được `Cm → Bb → Ab → G → Cm` trong khi phách mạnh là La♭. `Cm` không được loss 0 trên La♭. Ensemble khác vẫn lượng tử hóa như cũ.
2. **`sonatina`.** Phách mạnh là close, vận tốc theo bảng mục 5. Slur liền bậc gán trong renderer, và ô Torroba nằm trong `skip_bars` của `_slur()`. Nốt lấy đà là móc kép trước phách mạnh. Profile `"torroba"` cho phép bè trung vượt 65 khi còn dưới bè cao. Đây là pattern của rally và selloff ở 4/4.
3. **`danza` và `fandanguillo`.** Đủ lưới 4/4, 6/8 và 3/4 ở mục 5. Hợp âm tối đa ba tiếng, nốt trên là giá của móc đó, viết ít nhất 68. Cùng profile `"torroba"`. `_shape_dynamics` lấy một `extra` cho cả ô. Snap 68/70, `_is_target` là bè cao có accent.
4. **`castillo`, ô thở, harmonics đúng cao độ, khung intro/outro, bốn hàng `PROFILES`.** `castillo` không snap. `sonatina` snap 66/68. Humanize trần 73 đọc vận tốc sau sóng.

Bước 1 và 2 đủ cho một ngày `1D`. Hai điệu vũ và *Castillos* là lớp sau, khi dialect đã đứng.
