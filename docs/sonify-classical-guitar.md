# Guitar cổ điển: variant thứ năm, một nhạc cụ, tối đa ba bè

> **Trạng thái**: Bản v10 (2026-10-23), chưa triển khai. Kiến trúc, đường xuất part, ràng buộc cao độ vang, luật chọn lớp, chính sách sửa nốt, và dialect hòa âm (mục 3.4) là **đã chốt để code theo**. Dialect hiện chỉ `villa` đăng ký; Sor và Barrios đi `COMMON`. Lưới tremolo giảm đếm theo phách của meter (mục 4.3.4). Sus không thắng F bằng phạt chất 0.35: khoản màu 0.70 chỉ trừ khi đã có hợp âm trước, cùng gốc, phách mạnh là âm màu, và lần đổi màu đi từ hợp âm ba cha — kể cả ô mở câu (mục 3.4). Âm màu chỉ được tính khi gốc đó đang được giữ. Các bảng figuration cụ thể vẫn là giả thuyết cho đến khi catalog Bước 0b xong; Bước 1 chỉ code khung, hàm chọn lớp, bộ sửa nốt và những pattern đã khóa ở mục 4, phần catalog-dependent để sau cờ bật/tắt rõ ràng. Dialect Barrios và lớp tiết tấu choro nằm ở [`docs/sonify-barrios-harmony.md`](./sonify-barrios-harmony.md), làm sau Bước 4, không thuộc các bước của file này.
>
> **Liên kết**: Pipeline hiện tại nằm ở [`docs/sonify-explain.md`](./sonify-explain.md) (giọng nhà, mode, nhịp, form theo khung `1D–1Y`), [`docs/sonify-instrument-sets.md`](./sonify-instrument-sets.md) (bộ nhạc cụ MuseSounds của 4 variant hiện tại) và [`docs/sonify-long-form.md`](./sonify-long-form.md) (form nhiều chương, trần thời lượng `47:21` cho bản `1Y`).

---

## 1. Ý tưởng và quyết định cốt lõi

Thêm **Guitar cổ điển** thành variant thứ năm, bên cạnh `symphony`, `jazz`, `minimalist`, `ambient`. Khác bốn variant kia, variant này chỉ có **một nhạc cụ thật duy nhất**: một cây guitar cổ điển dây nylon. Tính đa bè đến từ chính cây đàn, không phải từ nhiều part nhạc cụ khác nhau.

Ba lựa chọn cho người nghe, tương ứng ba phong cách viết cho guitar:

| Lựa chọn (ensemble id) | Nhãn UI đề xuất | Cảm hứng | Tính chất chính |
|---|---|---|---|
| `classic` | Cổ điển · Sor | Fernando Sor — không chỉ các study Op. 31/35 mà cả *Grand Solo* Op. 14 và *Fantaisie élégiaque* Op. 59 | Ba lớp chất liệu theo tính cách thị trường: study cân đối cho đoạn đi ngang, biến tấu hào hùng kiểu *Grand Solo* cho đoạn tăng/giằng co, hành khúc tang và giai điệu than kiểu *Fantaisie élégiaque* cho đoạn giảm/chương chậm (chi tiết mục 4.1) |
| `villa` | Hiện đại · Villa-Lobos | Heitor Villa-Lobos — *12 Études* No. 1, 2, 7 và đặc biệt No. 11, cùng *Préludes* | Mẫu arpeggio lặp xuyên ô nhịp (No. 1), arpeggio rộng và chạy bậc thang (No. 2/7), và viết giai điệu nằm trên hợp âm — chord-melody chậm, dồn dập — kiểu Étude No. 11 cho chương chậm và đoạn tích lũy (chi tiết mục 4.2) |
| `barrios` | Tremolo · Barrios | Agustín Barrios — *El Último Trémolo*, *Sueño en la Floresta*, và *La Catedral* (Preludio Saudade, Andante Religioso, Allegro Solemne) | Không chỉ tremolo: một cung hình thu nhỏ kiểu *La Catedral* — mở đầu bằng motif chuông/harmonics và arpeggio mơ của Preludio, thân bài là tremolo `p–a–m–i` giữ giai điệu ngân, cao trào và kết câu bằng những đoạn chạy dây nhanh kiểu Allegro Solemne (chi tiết mục 4.3) |

Các quyết định đã chốt trong kế hoạch này:

1. **Dùng lại trục `variant` × `ensemble` sẵn có** thay vì tạo ba variant riêng. `variant = "guitar"` là cây đàn và cách viết một-nhạc-cụ; `ensemble` chọn phong cách (`classic` = Sor, `villa`, `barrios`). Cách này khớp mô hình hiện tại: mọi variant đều có `classic` là hàng mặc định cộng hai hàng phụ, cache key đã gồm cả variant lẫn ensemble (`RecapStore._tag` trong `backend/app/sonify/audio.py`), và UI đã có sẵn hàng chọn ensemble thứ hai (`ENSEMBLE_ROWS` trong `src/api/client.ts`). Điểm khác: ở bốn variant cũ, ensemble chỉ đổi nhạc cụ; ở guitar, ensemble đổi **thuật toán viết bè**. Đây là mở rộng ngữ nghĩa có chủ đích, cần ghi rõ trong docstring của `ensemble.py`.
2. **Ba bè tối đa, mỗi bè một nốt tại một thời điểm**: **Cao** (giai điệu giá), **Trung** (hòa âm/arpeggio), **Trầm** (bass theo gốc hợp âm). Không hợp âm khối 4–5 nốt như piano. Khi hợp âm có 4–5 âm (7th, 9th, 7sus4, add9), phải **tỉa bè** theo thứ tự ưu tiên ở mục 5.3 và qua ống sửa nốt ở mục 5.5. Hợp âm `suspended` giữ quãng 2 hoặc quãng 4 đến cùng; quãng 5 bị bỏ trước.
3. **Nhãn không được trùng**: Id `guitar` trên cả hai trục dùng được vì cache tách bạch — variant guitar ra stem `guitar`, `guitar-villa`, `guitar-barrios`, còn ensemble dây thép của minimalist là `minimalist-guitar`. Nhưng nhãn UI phải phân biệt: variant mới là **«Guitar»**, hàng ensemble của minimalist đổi nhãn từ «Guitar» thành **«Guitar thép»** (id `guitar` và giọng `Acoustic Steel Plucked` giữ nguyên, chỉ đổi nhãn hiển thị trong `ENSEMBLE_ROWS` và `docs/sonify-instrument-sets.md`).
4. **Nhịp điệu phải đổi thật, không phải mọi thứ đều 4/4**: Guitar có bản đồ meter riêng (mục 4.0) — chương chậm của bản dài là **3/4** và scherzo là **6/8** (hoán đổi so với giao hưởng, giữ nguyên số ô/BPM/đồng hồ), trong chương còn đổi nhóm phách (hành khúc, hemiola, lệch 3+3+2) và đổi mật độ chia nhỏ (móc đơn → móc kép tremolo/chạy dây). Mọi pattern viết theo `active_meter()`, cấm khóa cứng lưới 4/4. Hai thứ cố ý không làm: đổi ký hiệu nhịp giữa chương và rubato — cả hai phá các giả định một-meter-mỗi-chương và phép tính thời lượng/playhead hiện tại.
5. **Hòa âm theo dialect, mặc định là catalog chung.** `plan_slots` nhận một `HarmonyDialect` (mục 3.4). Sor (`classic`) và Barrios dùng `COMMON` — đúng catalog và ma trận Markov hiện tại. Chỉ `villa` đăng ký dialect riêng, vì sus và add9 của Villa-Lobos phải có mặt lúc Viterbi chọn hợp âm thì giai điệu mới hát được những nốt đó. Dialect sau này cho Sor hoặc Barrios là một lớp mới cộng một dòng trong bảng đăng ký; vòng Viterbi không có tên phong cách nào cứng trong code. Plan đó cho Barrios — vòng quãng 5, Napolitaine, chuỗi át của choro, và lớp tiết tấu đi kèm — nằm ở [`docs/sonify-barrios-harmony.md`](./sonify-barrios-harmony.md), ngoài các bước của file này.

Không làm trong giai đoạn đầu: live stream (`StreamVariant` trong `backend/app/sonify/voices.py`/`stream.py` phát bằng sóng synth, không có tiếng gảy), và ký hiệu ngón tay/dây (fingering) in trên bản nhạc.

---

## 2. Vì sao guitar hợp với dữ liệu này

- **Khoảng âm đủ rộng**: Guitar cổ điển chuẩn (dây buông E2–A2–D3–G3–B3–E4, MIDI phát âm 40–45–50–55–59–64) chơi thực tế tới khoảng B5 (MIDI 83, phím 19 dây 1). Vùng "ngọt" cho cả ba bè là E2–E5 (40–76) — khoảng 3 quãng tám, đủ cho đường giá đã lượng tử hóa, mà không cần gập quãng tám thô bạo như khi ép vào một nhạc cụ hơi hẹp.
- **Đa bè thật trên một nhạc cụ**: Ngón cái (`p`) gánh bass, ngón `i/m` gánh bè giữa, ngón `a/m` gánh giai điệu — đúng cấu trúc ba lớp mà dữ liệu đã có sẵn (giá → giai điệu, hợp âm → bè đệm, gốc hợp âm → bass). Bốn variant hiện tại phải dùng 3–5 nhạc cụ khác nhau để diễn đạt ba lớp này.
- **Âm sắc gảy có decay tự nhiên**: Nốt guitar tắt dần sau tiếng gảy, nên nốt giá đứng yên (sideways) nghe thành nốt ngân lặng thay vì tiếng synth/organ kéo đều — hợp với các phiên đi ngang nhiều như trên HOSE.
- **Mật độ nốt điều khiển được bằng một tay**: Cùng một lưới móc đơn, chỉ cần đổi pattern tay phải (gảy rời → arpeggio cuộn → tremolo) là đổi hẳn cảm giác thanh khoản, mà không cần thêm nhạc cụ percussion như `minimalist`.

---

## 3. Ánh xạ dữ liệu → ba bè (phần chung cho cả ba phong cách)

Tái dùng tối đa pipeline hiện tại trong `backend/app/sonify/render.py::_compose`: chuỗi đóng cửa → `raw_pitches` trên thang → `plan_slots` (Viterbi Markov chọn hợp âm từng ô) → `plan_phrases` → `band_at` (thanh khoản `p–f`). Module guitar nhận đúng các đầu vào mà `render_jazz_score`/`render_minimalist_score` đang nhận (`slots`, `pitches`, `phrases`, `band_at`, `chord_at`, `dynamics`, `rel_span`...). Sor và Barrios dùng `slots` của dialect `COMMON`. `villa` lập `slots` bằng dialect của mình (mục 3.4) rồi mới viết bè — sus phải thắng ngay trong `plan_slots`, trước `quantize_strong_beats`, vì bước lượng tử hóa hút phách mạnh về âm của hợp âm đã chọn.

| Nguồn dữ liệu / tầng sẵn có | Bè Cao (giai điệu) | Bè Trung (đệm) | Bè Trầm (bass) |
|---|---|---|---|
| Giá đóng cửa (`raw_pitches`, `quantize_strong_beats`) | Đường giai điệu chính, phách mạnh bắt âm hợp âm như hiện tại | — | — |
| Hợp âm ô nhịp (`slots`/`chord_at`) | Âm hợp âm ở phách mạnh | Âm 3, âm 7/9; với hợp âm `suspended` của dialect `villa` thì là quãng 2, quãng 4 hoặc b7 (mục 3.4, 5.3) | Gốc hợp âm; phách 3 có thể là quãng 5 (`fifth_above_bass`) |
| Thanh khoản cửa sổ 2 ô (`band_at`: `p/mp/mf/f`) | Nhấn (accent) ở đỉnh câu, velocity | **Mật độ pattern**: thưa → arpeggio đầy → tremolo (xem bảng từng phong cách) | Số lần đánh trong ô: `p` 1 nốt → `f` theo pattern |
| Câu nhạc (`phrases`, `phrase.apex`, `phrase.closes`) | Slur theo câu, hairpin về đỉnh câu, accent ở nốt breakout (tái dùng `techniques`, `hairpins`) | Fill arpeggio ngắn ở cuối câu đóng, giống vai `fills()` của piano hiện tại | Nốt dẫn (approach) về gốc ô sau ở cuối câu |
| Regime/character/mode (`movement_character`, Trưởng/Thứ cùng tên) | Giữ nguyên quy tắc mode hiện tại | Sor/Barrios: màu mượn như hiện tại. Villa: dialect mục 3.4, nudge character dưới 0.1 | Giữ nguyên |
| Đỉnh giá cao / breakout | Nốt điểm cao tenuto, thưa (tương đương vai flute/vibraphone cũ nhưng vẫn trên cùng cây đàn) | — | — |

### 3.1. Âm vực ba bè — bảng tính trên cao độ vang, renderer dùng biên viết đã dịch

Mọi giới hạn trong bảng này là **cao độ vang** (sounding pitch) — nhưng đó là ngôn ngữ của phép tính phím và của test, không phải của renderer. Renderer **không** cộng `key.semitones` vào nốt để so với bảng này: nó so **số viết** trong không gian Đô với các biên đã dịch ở mục 3.3 (chính bảng này trừ `semitones`), và mọi thao tác của nó — gập bass, tỉa bè, nâng/đổi bè Trung ở mục 5.5 — đều chạy trên số viết. Chỉ hai nơi được quy về cao độ vang: bên trong phép gán dây/phím ở mục 5.2 (`midi + semitones` để tính phím) và test. `<octave-change>-1` ở khuông guitar (mục 6.1) chỉ là ký hiệu viết cao hơn tiếng thật một quãng tám; nó không cộng gì vào cao độ vang và không được tính vào phím.

| Bè | Dải vang cho phép | Dải vang ưu tiên | Ràng buộc |
|---|---|---|---|
| Trầm | 40–53 (E2–F3) | Gốc hợp âm đặt trong 40–51 | Chỉ dây 6/5/4; không bao giờ dưới E2 (40). Mọi nốt bass tính ra (gốc, quãng 5, "quãng 8") phải **gập theo lớp pitch-class vào dải này** (cộng/trừ 12 cho đến khi lọt) trước khi viết — phép gập chạy trên số viết trong không gian Đô theo biên đã dịch, xem mục 3.3 và 5.5 |
| Trung | 50–65 (D3–F4) | 53–62 | Âm hợp âm gần nhất theo chuyển bè của profile lớp (mục 5.4); tránh trùng dây với bè Cao khi cùng lúc. **Ngoại lệ hợp âm khối** (fanfare Grand Solo, chord-melody Étude 11): bè Trung được rời trần 65 để lên ngồi ngay dưới giai điệu trong cùng thế tay — điều kiện ở mục 5.2 |
| Cao | 59–81 (B3–A5) | 62–79 (D4–G5) | Trần cứng vang 83. Trong dải 59–81, trên 79 chỉ cho đỉnh câu/breakout; ngoài dải — vùng 82–83 — chỉ cho nốt chuông Preludio (có dùng vùng này hay khóa chuông ở 81 là câu hỏi mở chốt ở Bước 0, mục 9). Đỉnh đường giá không bao giờ vượt 81 |

Bảng trên là cao độ **vang**. `NoteEvent.midi` trong score luôn ở không gian Đô, nên khi renderer viết nốt, mọi biên trong bảng phải trừ `key.semitones` trước (các trường đã dịch ở mục 3.3); cao độ vang `midi + key.semitones` chỉ xuất hiện trong phép tính phím (mục 5.2) và trong test.

Chồng lấn giữa các dải là cố ý (guitar thật vẫn vậy), nhưng khi cả ba bè **cùng vang tại một thời điểm đánh**, thứ tự là nghiêm ngặt **Trầm < Trung < Cao** — Trung không bao giờ trùng hay cao hơn giai điệu đang vang (khớp mục 5.3 và lớp Pattern của Villa). Bè Trung chỉ được là nốt cao nhất khi bè Cao đang nghỉ; bè Trầm luôn là nốt thấp nhất.

### 3.2. Nén đường giá vào âm vực guitar

Đường giá thô hiện chạy trên thang Đô3–Đô7 (`SCALE_LOW = 48`, `SCALE_HIGH = 96` trong `quantize.py`) — rộng hơn âm vực guitar nhiều. Không gập từng nốt theo modulo 12 (sẽ làm đường giá gãy khúc). Dùng lại ý tưởng của `_sax_melody_curve` trong `jazz.py` nhưng **không chép nguyên tập ứng viên của sax**: sax chỉ bị trần nên chỉ dịch xuống (0/−12/−24); thang giá 48–96 có cả những câu nằm hẳn *dưới* sàn bè Cao, và một câu dưới sàn không hề "rộng hơn âm vực" nên điều kiện nén sẽ không bao giờ kéo nó lên — câu đó sẽ rơi vào vùng Trung/Trầm và giết tremolo cả câu. Dynamic programming của guitar chọn mức dịch trong **{+12, 0, −12, −24}** cho mỗi `Phrase` sao cho câu nằm trong cửa sổ viết [`guitar_treble_floor`, `guitar_treble_top`] (không gian Đô, mục 3.3), phạt nhảy ngược hướng giá và nhảy lớn ở biên câu. Điều kiện nén phải giống sax, không được hẹp hơn: **sau mức dịch đỡ lệch nhất, chỉ cần còn một nốt nằm ngoài cửa sổ là nén** monotone khoảng cách theo bậc thang vào dải đích, rồi `quantize_strong_beats` lại trên thang đã nén — đúng quy trình `_compress_phrase_to_bounds` của jazz. Không chờ "câu rộng hơn cửa sổ" mới nén: một câu 50–70 rộng 20 nửa cung, hẹp hơn cửa sổ 59–81 (22 nửa cung), nhưng không mức dịch nào đặt vừa cả câu (+12 thành 62–82 vượt trần, 0 còn nốt dưới sàn) — câu như vậy vẫn phải nén sau khi dịch. Tremolo (mục 4.3) dùng cùng đường giai điệu đã nén này, chỉ đổi cách lặp nốt.

### 3.3. Dịch giọng nhà và quy đổi về không gian Đô

Giữ nguyên cơ chế `KeySpec` (±3 nửa cung: VNM–Đô `0`, FPT–Rê `+2`, HPG–Mi♭ `+3`, VCB–Si♭ `−2`, GMD–La `−3`): soạn trong không gian Đô, MusicXML cộng `key.semitones` khi xuất. Vì 4/5 giọng nhà không phải Đô, `register_for` trong `keys.py` phải bổ sung các trường guitar dịch **cả hai chiều** theo đúng cách `synth_low`/`synth_high` đang làm (`bound − semitones`), không theo cách nửa vời của `violin_lowest` (chỉ nâng sàn khi dịch xuống):

```python
guitar_floor         = 40 - key.semitones   # sàn Trầm vang E2, quy về số viết không gian Đô
guitar_bass_top      = 53 - key.semitones   # trần Trầm vang F3
guitar_mid_low       = 50 - key.semitones   # sàn Trung vang D3
guitar_mid_high      = 65 - key.semitones   # trần Trung vang F4 (trừ ngoại lệ hợp âm khối, mục 5.2)
guitar_treble_floor  = 59 - key.semitones   # sàn Cao vang B3
guitar_treble_top    = 81 - key.semitones   # trần của đường giá: đỉnh/breakout nằm trong cửa sổ này, không vượt
guitar_ceiling       = 83 - key.semitones   # trần cứng vang; khoảng (treble_top, ceiling] chỉ cho nốt chuông Preludio
```

Bảy trường này là **biên của số viết** (`NoteEvent.midi` trong không gian Đô): renderer gập/tỉa/nâng nốt hoàn toàn bằng các biên này và không bao giờ viết một cao độ vang vào score. Cao độ vang `midi + key.semitones` chỉ được tính ở hai nơi: phép gán dây/phím (mục 5.2) và test. Renderer và `assert_playable` chỉ đọc các trường này từ `active_register()` (đã được `compose_register` đặt theo giọng của bài), không tự cộng/trừ `semitones` rải rác. Mọi test âm vực/gập nốt phải chạy cả năm giọng nhà và ít nhất một test phải dùng giọng khác Đô (ví dụ FPT `+2`) — test ở Đô không bắt được lỗi lẫn hai không gian, vì ở Đô hai hệ số trùng nhau.

### 3.4. Dialect hòa âm — vỏ dùng chung, hiện chỉ Villa-Lobos đăng ký

Chất Villa-Lobos nằm ở hợp âm, không chỉ ở cách gảy. Sus của ông thay âm ba bằng quãng 2 hoặc quãng 4; add9 giữ âm ba và thêm quãng 9 mà không kèm âm 7; một số ô trượt nguyên một hình xuống một cung (`C` → `B♭`, `F` → `E♭`). `jazz_chord` không làm được việc này: nó chạy sau `quantize_strong_beats` và chỉ thêm âm 7/9 lên hợp âm đã chọn, nên nốt phách mạnh vẫn là âm ba. Sus phải là ứng viên trong catalog mà Viterbi nhìn.

Vỏ nằm ở module mới `backend/app/sonify/harmony.py`. `plan_markov_chords` / `plan_slots` nhận một dialect; vòng lặp không nhắc tới `villa`, `classic` hay `barrios`. `_compose` lấy dialect bằng `dialect_for(ensemble)` ngay trước `plan_slots`.

```python
class HarmonyDialect:
    name: str

    def extra(self, mode: Literal["major", "minor"]) -> tuple[Chord, ...]:
        """Hợp âm thêm bên cạnh CHORDS (trưởng) hoặc MINOR_CATALOG (thứ). COMMON trả rỗng."""

    def transition(self, prev: Chord, curr: Chord, mode: str) -> float | None:
        """Trọng số mức gốc khi một trong hai hợp âm thuộc dialect này.
        None: cặp không thuộc dialect, bảng Markov hiện tại quyết định.
        0: cặp bị cấm. Số dương là xác suất mức gốc, không nhân 2."""

    def shares_root(self, prev: Chord, curr: Chord) -> bool:
        """Cùng root_step và alter, và một bên có quality_group == "suspended".
        COMMON trả False. Add9 không đi cửa này: cả hai đều nhóm "major"."""

    def allowed(
        self, chord: Chord, *, pedal: bool, phrase_downbeat: bool,
        character: MovementCharacter | None, mode: str,
    ) -> bool: ...

    def bias(self, chord: Chord, character: MovementCharacter | None, mode: str) -> float:
        """Chỉ để phân hòa. Trị tuyệt đối dưới 0.15, nhỏ hơn STRONG_BEAT_WEIGHT (2.5)."""

    def color_credit(
        self, chord: Chord, strong_pitch_classes: frozenset[int], prev: Chord | None,
    ) -> float:
        """Trừ vào phát xạ của ô. COMMON trả 0. Villa trả 0.70 hoặc 0, đúng một lần mỗi ô."""


DIALECTS: dict[str, HarmonyDialect] = {"villa": VillaDialect()}

def dialect_for(ensemble: str) -> HarmonyDialect:
    return DIALECTS.get(ensemble, COMMON)
```

`COMMON.extra` rỗng, `COMMON.transition` trả `None`, `COMMON.shares_root` trả `False`, `COMMON.bias` trả 0, `COMMON.allowed` trả `True` với mọi hợp âm, `COMMON.color_credit` trả 0 kể cả khi `prev` là `None`. Hợp âm không thuộc `extra()` của dialect đang chạy vẫn đi qua `_borrowed_allowed` đúng chỗ cũ; `allowed` của dialect không thay cổng đó. Sor (`classic`) và Barrios không có dòng trong `DIALECTS`, nên chúng đi đúng catalog, ma trận `_ROOT_TRANSITIONS`, cổng `_borrowed_allowed` và `chord_bias` như symphony. Đăng ký dialect cho một trong hai phong cách đó về sau là viết một lớp và thêm một khóa vào `DIALECTS`.

Trong vòng Viterbi, khi `prev` hoặc `curr` thuộc `extra()` của dialect đang chạy:

- Cặp khác gốc lấy `root_prob` từ `dialect.transition` và tính `−0.6·ln`. Không đi nhánh `prob * 2.0`: nhánh đó giả định mỗi gốc đúng hai hợp âm (ba và bảy). Nhét sus vào `CHORDS` làm hàng xác suất không còn cộng thành 1. Cặp cùng gốc không dùng số này để tính giá — xem gạch ngay dưới.
- `same_root` là `same_harmonic_root(prev, curr) or dialect.shares_root(prev, curr)`, ở cả ba nhánh mode của vòng lặp. `VillaDialect.shares_root` trả đúng khi cùng `root_step` và `alter`, và một bên có `quality_group == "suspended"`. `same_harmonic_root` trả sai cho `C` và `Csus4`: nhóm `"suspended"` khác `"major"`, và ngoại lệ major/dominant chỉ nhận hợp âm nằm trong `CHORDS`. Không có `shares_root` thì bảng giá cùng gốc bên dưới không chạy cho sus ở nhánh borrowed trưởng. Add9 không cần cửa này: `C` và `Cadd9` đều nhóm `"major"`, `same_harmonic_root` đã nhận. Nhánh thứ đang so `root_step` với `alter` nên sus đã cùng gốc; vẫn OR `shares_root` để một định nghĩa phủ cả hai mode. `held_bars` không reset khi đổi màu trên cùng gốc.
- Giá cùng gốc đi đúng các nhánh sẵn có của `form.py`, nên bảng ở dưới là giá thật, không phải chỉ phạt chất 0.35. `held_bars == 1` và không mở section: `SECOND_BAR_STAY_COST` 0.15 cộng phạt chất 0.35, cạnh không vào giá. `held_bars >= 2`: `−0.6·ln(trọng số) + EXTENDED_STAY_PENALTY` 0.25 cộng phạt chất. Ô mở section không đi nhánh ở-lại: chỉ `−0.6·ln(trọng số)` cộng phạt chất. Giữ đúng một hợp âm villa không có self-edge thuận thang, nên dùng `BORROWED_HOLD_PROB` 0.16 ở nhánh giữ đã có. `held_bars` không reset khi đổi màu trên cùng gốc.
- Hợp âm dialect không nằm trong `allowed_tonics`, nên ô pedal (`intro` / `outro` / `warmup` / `cooldown`) vẫn chỉ hợp âm chủ.

Một phách mạnh lệch một bậc thang bị phạt 2.5 (`STRONG_BEAT_WEIGHT`). Nốt đó thường nằm trong nhiều hợp âm một lúc: F thuộc `Csus4`, và cũng thuộc F, Fmaj7, Dm, Dm7. Hòa phát xạ thì giá chuyển tiếp quyết định, và giá đó không phải mỗi phạt chất 0.35. Với công thức hiện tại trong `form.py`, từ gốc C đang giữ:

| Trạng thái | `C` → `Csus4` nếu để cạnh 0.30 đi vào `−0.6·ln` | `C` → `F` (xác suất gốc 0.26) |
|---|---|---|
| `held_bars == 1`, không mở section | 0.15 + 0.35 = 0.50. Cạnh 0.30 không vào giá | 0.81 + phạt đổi ô 0.45…0.80 |
| `held_bars >= 2` | `−0.6·ln(0.30) + 0.25 + 0.35 ≈ 1.32` | 0.81, không phạt đổi ô |
| Ô mở section | `−0.6·ln(0.30) + 0.35 ≈ 1.07` | 0.81 |

`held_bars >= 2` là trạng thái đứng của một gốc đã giữ từ hai ô (`EXTENDED_STAY_PENALTY` chỉ cộng ở nhánh này). Ở đó F rẻ hơn `Csus4`, Dm cũng rẻ hơn (`C` → `D` là 0.14, giá ≈ 1.18), và cả hai đều chứa F. Ô đầu bài không có chuyển tiếp. So sánh bias một mình — F 0.04 đối sàn hợp âm lạ 0.08 — chỉ ra F ở uptrend và downtrend khi character không phải `selloff`. `selloff` trừ 0.08 cho Dm; Dm chứa F và còn khoảng −0.02, rẻ hơn F. Sideway đặt bias của F ở 0.20, sàn 0.08 rẻ hơn F. F không bị hút về E. Một giá phẳng 0.50 cho mọi lần đổi màu cũng không dùng được: từ ô thứ ba, ở-lại trên C khi giai điệu chỉ là C hoặc G tốn khoảng 1.28, trong khi 0.50 rẻ hơn cả lần ở-lại đó, nên sus bị trải lên những ô không có quãng 4.

Dialect trừ một **khoản màu** vào phát xạ, đúng một lần mỗi ô, qua `color_credit`. `chord_bias` cộng vào cùng phát xạ đó. Bảng ở trên chỉ là giá chuyển tiếp (`held_bars >= 2` là 1.32 đối 0.81), chưa cộng bias: sàn của hợp âm không nằm trong `CHORDS` là 0.08, F ở uptrend và downtrend là 0.04, `rally` trừ thêm 0.08 cho F (`_DIATONIC_DELTA`) và dialect trừ 0.04 cho sus4. Người thắng là tổng của cả ba.

Khoản trừ vào phát xạ chỉ khi đủ cả bốn điều. `color_credit` xét ba điều đầu và trả 0.70 hoặc 0. Điều thứ tư nằm trong vòng Viterbi, vì hàm không biết `prev_held`. Thiếu một điều thì khoản là 0:

- Đã có hợp âm trước. Ô đầu bài (`prev is None`) không được khoản. Nếu vẫn trừ 0.60, uptrend ra `Csus4` ở `0.08 − 0.60 = −0.52`, rẻ hơn F ở 0.04 khoảng nửa đơn vị.
- Cùng gốc với hợp âm trước (`root_step` và `alter`). Hợp âm khác gốc không được khoản, dù phách mạnh trùng âm màu của nó.
- Một phách mạnh là âm màu của chính hợp âm villa đó: quãng 4 của sus4 và của 7sus4, quãng 2 của sus2, quãng 9 của add9, b7 của 7sus4. Gốc và quãng 5 không được khoản.
- Lần đổi màu chỉ được khoản khi hợp âm trước là hợp âm ba cha (`C` → `Csus4`), kể cả ô giá 0.15 và ô mở câu. Giữ đúng hợp âm ở ô giá 0.15, đổi giữa hai màu villa, và `Dm7` → `D7sus4` đều không được. `Dm7` không phải hợp âm ba của Rê, Đô là b7 của `D7sus4`, và `0.15 + 0.35 − 0.70` âm. Câu mới không nới điều này: ba ô toàn Đô, `selloff`, câu mới ở ô 2, ra `Dm7, D7sus4, D7sus4` trong khi `COMMON` ra `C7, F, F`. Bỏ khoản của hợp âm cha thì hai ô, ô sau là Fa, mở bằng `Fmaj7`. Lần giữ từ ô thứ ba vẫn trừ 0.70.

0.70 lớn hơn 0.62 và nhỏ hơn một phạt phách mạnh 2.5. 0.60 không giữ được sus khi F còn ở phách mạnh. Nhánh giữ bằng `BORROWED_HOLD_PROB` 0.16 là khoảng 1.35; trừ 0.60 còn 0.75; cộng sàn 0.08 và mức `rally` −0.04 của sus4 thành khoảng 0.79. Cùng lúc `rally` kéo F xuống `0.81 + 0.04 − 0.08 = 0.77`. F rẻ hơn. Với 0.70, nhánh giữ ở `rally` còn `1.35 − 0.70 + 0.04 = 0.69`, dưới 0.77. Character khác không trừ 0.08 cho F: giữ sus còn `1.35 − 0.70 + 0.08 = 0.73`, F còn `0.81 + 0.04 = 0.85`.

Hệ quả khi gốc trước là C và mọi phách mạnh thuộc {C, F}. Cả F lẫn `Csus4` đều mất 0 ở phát xạ trên tập phách mạnh đó. Một móc yếu lệch một bậc nặng 0.02 (`WEAK_BEAT_WEIGHT`), và trọng số này nhân theo từng móc trong run. Ca giữ `Csus4` ở `rally` chỉ rẻ hơn F khoảng 0.08 (0.69 đối 0.77). Bốn móc yếu của A — nốt có trong F, không có trong `Csus4` — nặng đúng 0.08, và F trở thành hợp âm rẻ hơn. Ca đó đòi mọi móc của ô thuộc {C, F}, không chỉ phách mạnh.

- Phách mạnh là F: `Csus4` thắng cả ba trạng thái, và thắng cả lần giữ tiếp. `held_bars >= 2` còn `1.32 − 0.70 + 0.08 = 0.70`, `rally` còn 0.66, đều dưới F (0.85, `rally` 0.77). Ô mở section còn `1.07 − 0.70 + 0.08 = 0.45`. `held_bars == 1` còn `0.50 − 0.70 + 0.08 = −0.12`, trong khi F còn cộng phạt đổi ô từ 0.45. Giữ tiếp `Csus4` còn 0.73, `rally` còn 0.69, đều dưới F. Ca `rally` của lần giữ chỉ đứng khi mọi móc của ô, không chỉ phách mạnh, thuộc {C, F}.
- Phách mạnh chỉ là C hoặc G: không có khoản. `Csus4` giữ giá chuyển tiếp 1.32 cộng sàn 0.08, thua F và thua lần ở-lại trên C (≈ 1.28). Không trải sus lên gốc.
- Phách mạnh có thêm A: `Csus4` mất 2.5 vì không chứa A. Khoản 0.70 không bù nổi, F hoặc Fmaj7 thắng.
- Ô đầu bài, chưa có hợp âm trước: khoản là 0. F thắng ở uptrend và downtrend khi character không phải `selloff`, vì 0.04 dưới sàn 0.08, và F không bị hút về E. `selloff` về Dm, không về F. Sideway không khóa về F. Ô pedal vẫn chỉ hợp âm chủ.
- Add9: E và D cùng ở phách mạnh thì D là quãng 9 của `Cadd9`, có khoản vì cùng gốc C. `Asus4` (A–D–E) và `A7sus4` cũng chứa cả E lẫn D, và D là quãng 4 của chúng, nhưng khác gốc nên khoản là 0. Từ C sang A là 0.24, giá `−0.6·ln(0.24) ≈ 0.86` cộng sàn 0.08 thành khoảng 0.94; `volatile` trừ 0.08 cho 7sus4 thì `A7sus4` còn khoảng 0.86. `Dsus2` (D–E–A) cũng chứa E lẫn D; nếu được khoản 0.70 theo quãng 2 thì từ C sang D (0.14) còn `1.18 − 0.70 + 0.08 = 0.56`, rẻ hơn 0.70 của `Cadd9`. Khác gốc nên không được khoản: giá còn khoảng 1.18 cộng 0.08. `Em7` chứa cả E lẫn D, nhưng cửa C → E là 0.08, giá khoảng 1.52 trước bias, vẫn trên 0.70. `Cadd9` ở `held_bars >= 2` là 0.70, ở ô mở section là `1.07 − 0.70 + 0.08 = 0.45`, ở `held_bars == 1` là −0.12. Cả ba đều dưới `Asus4` và `Dsus2`. Ô chỉ có E thì quãng 9 không ở phách mạnh, không có khoản; `held_bars == 1` ở-lại trên C tốn 0.15, đổi sang `Cadd9` tốn 0.50 cộng sàn 0.08, nên ra C hoặc Cmaj7. Am chứa E, nên test chỉ có E không khóa được add9.

**Điều kiện trên `Chord`, dùng cho mọi dialect không chồng âm ba.** `transpose_chord` trong `keys.py` đang đánh vần theo chồng âm ba (`index * 2`): `Csus4` (C–F–G) sẽ viết F thành E♯. Thêm trường `degrees: tuple[int, ...] = ()` trên `Chord`. Để trống thì đường cũ giữ nguyên (test dịch giọng hiện tại không đổi). Có giá trị thì chữ cái là gốc cộng `degrees[index]`, không phải `index * 2`. `quality_group` thêm `"suspended"` cho sus2, sus4 và 7sus4. Add9 giữ nhóm `"major"` vì còn âm ba. Hai nhóm này hiện chỉ được `ambient.py`, `form.py` và `same_harmonic_root` đọc.

| Hình | `kind` | `kind_text` | `degrees` | Ví dụ trong Đô | Ba nốt guitar giữ lại |
|---|---|---|---|---|---|
| sus4 | `suspended-fourth` | `sus4` | `(0, 3, 4)` | C–F–G | đủ ba |
| sus2 | `suspended-second` | `sus2` | `(0, 1, 4)` | C–D–G | đủ ba |
| add9 | `other` | `add9` | `(0, 2, 4, 1)` | C–E–G–D | bỏ quãng 5, còn 1–3–9 |
| 7sus4 | `suspended-fourth` | `7sus4` | `(0, 3, 4, 6)` | G–C–D–F | bỏ quãng 5, còn 1–4–b7 |

`fifth_above_bass` lấy quãng 5 ở `pitches[2]`. Mọi hợp âm villa giữ đúng thứ tự trong cột `degrees`: quãng 5 đứng thứ ba, quãng 9 và b7 không được đưa lên chỗ đó. Add9 thứ của bậc I là C–E♭–G–D, cùng `degrees` `(0, 2, 4, 1)`, dấu thăng giáng nằm ở âm ba của hợp âm cha.

Playback của ký hiệu `<harmony>` đã bị tắt trong `_mute_mscx_harmony`. Tiếng nằm ở nốt viết; chữ chỉ để đọc. Add9 không có kind MusicXML riêng, nên `other` với chữ `add9`.

**`VillaDialect` — luật dựng catalog**, sinh trong không gian Đô theo mode, rồi `transpose_chord` đẩy đi như mọi hợp âm khác. Gốc duyệt là gốc của catalog mode, không phải bảy chữ cái không dấu: trưởng là sáu gốc của `CHORDS` (C, D, E, F, G, A); thứ là gốc của `MINOR_DIATONIC` (C, D, E♭, F, G, A♭), bỏ `F#dim7`. Hợp âm villa chép `root_step` và `alter` của hợp âm cha. `Ebsus2` thứ là gốc `E` với `alter -1`, cùng `Eb`, không phải một chữ riêng — nếu không, `shares_root` và cửa `Ebsus2` → `E♭` không thấy chúng là một gốc. Với mỗi gốc đó, xét sus2, sus4, add9 và 7sus4, rồi bỏ theo hai luật:

1. Quãng màu (2, 4, 9, b7) không nằm trên thang của mode thì bỏ. Quãng 5 không nằm trong luật này: `D7sus4` thứ có quãng 5 là A, ngoài thứ tự nhiên, nhưng quãng 4 và b7 đều thuộc thang nên hợp âm vẫn được giữ. Phạt hòa với hợp âm ba là 0.05 (cùng cỡ `SEVENTH_TENSION_COST`).
2. Không còn pitch-class nào trên thang thì bỏ hẳn. `quantize_chord_tone` ném lỗi `"no chord tone in the melody register"` khi hợp âm không có âm nào để hát.

Add9 không đi hết gốc catalog. Trưởng chỉ bậc I, IV, V. Thứ chỉ bậc i và iv. Luật 1 một mình còn giữ `Ebadd9` (quãng 9 là F) và `Abadd9` (quãng 9 là Si♭), cả hai đều thuộc thứ tự nhiên. Kết quả đã lọc, để luật và danh sách không lệch nhau:

| | Trưởng | Thứ tự nhiên |
|---|---|---|
| sus2 | C, D, F, G, A. Bỏ `Esus2` (F♯) | C, E♭, F, A♭. Bỏ `Dsus2` (E) và `Gsus2` (A) |
| sus4 | C, D, E, G, A. Bỏ `Fsus4` (B♭) | C, D, E♭, F, G. Bỏ `A♭sus4` (D♭) |
| add9 | Chỉ I, IV, V: C, F, G. Âm ba là âm ba trưởng | Chỉ i và iv: `Cm add9`, `Fm add9`. Bỏ `Ebadd9`, `Abadd9` và `Gadd9` (A). Âm ba lấy từ hợp âm cha |
| 7sus4 | G, D, A, và `E7sus4` (E–A–B–D, cả bốn nốt thuận thang). Bỏ `C7sus4` (B♭) và `F7sus4` (B♭). B không phải gốc của `CHORDS`, nên không có `B7sus4` | C, D, F, G. A không phải gốc catalog thứ, nên không có `A7sus4`. Bỏ `E♭7sus4` và `A♭7sus4` (b7 hoặc quãng 4 là D♭) |

Add9 chỉ có việc khi cùng một ô có cả âm ba lẫn quãng 9. Sus2 đã bắt nốt 9 khi nó là phách mạnh một mình.

Trượt song song chỉ ở trưởng, xuống một cung, và chỉ hai hình còn nốt thuận thang: `Csus2` → `Bbsus2` (còn C, F) và `Fsus2` → `Ebsus2` (còn F). Ở thứ, `Absus2` và `Ebsus2` đã ra từ bảng sus2; `Bbsus2` không ra, vì Si♭ không phải gốc của `MINOR_DIATONIC`. Không chép danh sách trượt của trưởng sang thứ. Ký hiệu theo bass. Giai điệu hát nốt thuận thang; bass chromatic là hợp âm đệm, cùng hợp đồng với hợp âm mượn. Nốt dẫn bán cung ở móc cuối ô (bảng Pattern, band `f`) vẫn là figuration và không đổi ký hiệu.

`DAILY_ENSEMBLE_SPEC` và mọi spec dựng bằng `_spec` trong `span.py` đều `borrowed=True`: 12 hợp âm thuận thang cộng 12 hợp âm mượn. `extra()` trưởng thêm 19 hợp âm (5 + 5 + 3 + 4 + 2), thành 43 ứng viên, 86 trạng thái, so với 48 trạng thái của đường borrowed. Bước Viterbi tỉ lệ bình phương số trạng thái, nên đắt hơn khoảng ba lần, và chỉ ensemble `villa` trả giá đó. Mode thứ không cộng `BORROWED` (`catalog = MINOR_CATALOG` trong `plan_markov_chords`): 12 hợp âm catalog cộng 15 màu villa.

**`VillaDialect.transition`** trả một trọng số, xét đúng thứ tự này, cặp khớp trước thì dừng:

1. Mode trưởng, và một trong hai hợp âm là hợp âm trượt của trưởng (`Bbsus2`, `Ebsus2`). Chỉ bốn cặp sau khác 0: `Csus2` → `Bbsus2` và `Fsus2` → `Ebsus2` là 0.22; `Bbsus2` → `F` và `Ebsus2` → `F` là 0.34. Mọi cặp khác có một đầu là hợp âm trượt của trưởng trả 0. `Ebsus2` trưởng chỉ còn một nốt thuận thang là F; không mở thành «mọi hợp âm chứa F» (Dm, `Csus4`, Fmaj7 đều không được cửa). Ở thứ, `Ebsus2` không thuộc danh sách này: nó là sus2 thuận thang của gốc E♭, đi cửa 2–6, và `Ebsus2` → `E♭` lấy 0.40. `Bbsus2` không có trong `extra()` thứ.
2. Cùng gốc, hợp âm hiện tại là hợp âm ba cha, hợp âm trước là màu villa của gốc đó: 0.40. `Csus4` → `C` đi cửa này, không đi cửa 0.30.
3. Cùng gốc, một bên là màu villa của gốc đó: 0.30.
4. Hợp âm hiện tại là màu villa của gốc X, và `_ROOT_TRANSITIONS` có cửa từ gốc của hợp âm trước sang X: lấy xác suất gốc đó, không nhân 2. `G` → `Csus4` cùng cửa với `G` → `C`. Cùng `root_step` mà khác `alter` thì không có cửa: `Ab` không lấy self-loop 0.18 của `A`, `Eb` không lấy self-loop của `E`, `F#dim7` không lấy hàng `F`. Hai chữ khác nhau vẫn tra bảng, kể cả khi một bên là Mi♭. `Eb` → `Fsus2` là cửa `E` → `F` (0.22), `C` → `Ebsus4` là `C` → `E` (0.08).
5. Hợp âm trước là màu villa của gốc X và hợp âm hiện tại thuận thang có cửa từ X: lấy xác suất gốc đó, cùng điều kiện cùng chữ thì phải cùng `alter`. `Ebsus4` → `Fm` là cửa `E` → `F` (0.22).
6. Còn lại: 0 nếu một bên thuộc `extra()`, `None` nếu không bên nào thuộc — bảng Markov cũ quyết định.

Từ `held_bars >= 2` và ở ô mở section, các số 0.30 và 0.40 đi vào `−0.6·ln` rồi cộng phạt chất. Chúng chỉ bị bỏ qua khi `held_bars == 1` và ô không mở section (nhánh `SECOND_BAR_STAY_COST`). Thứ tự trên quyết định số nào được log: `Csus4` → `C` lấy 0.40, không lấy 0.30. Khoản màu 0.70 trừ vào phát xạ, không đổi các trọng số này.

**`VillaDialect.allowed`**: trả `True` với hợp âm không thuộc `extra()`, để `_borrowed_allowed` chạy tiếp. Pedal trả `False` cho mọi hợp âm villa (khớp `allowed_tonics`). Hợp âm trượt không đứng ở phách đầu câu. Sus thuận thang được đứng ở phách đầu câu, nhưng âm màu chỉ được tính là âm hợp âm khi gốc đó đang được giữ. Ô đầu bài chưa có gốc, và mọi ô mà hợp âm trước khác gốc, đều chấm phát xạ như hợp âm cha. Nếu không, `Gsus4` hát Đô với phát xạ 0, hai ô chỉ đắt hơn chủ khoảng 0.31, rồi cửa Sol → Đô khoảng 0.42 rẻ hơn lần ở-lại trên chủ khoảng 1.28. Thứ `rally` ra `Gsus4, Gsus4, Cm` trong khi `COMMON` ra `Cm, Cm, Fm`. Trưởng không có character cũng vậy, ra `Gsus4, Gsus4, C`. Ba ô toàn Fa thì ra `G7, G7, Csus4`: Fa nằm trong `G7` và là quãng 4 của `Csus4`, phát xạ 0, cửa Sol → Đô rẻ hơn lần ở-lại trên `G7`. `COMMON` ở `rally` ra `F, F, G7`. Thứ, ba ô toàn Mi♭ ở `selloff` hoặc `volatile` ra `Cm, Cm, F7sus4`: Mi♭ là b7, cùng cửa Đô → Fa với `Fm7`, mức −0.08 cộng phạt bốn nốt 0.05 vẫn rẻ hơn khoảng 0.03. `COMMON` ra `Cm, Cm, Fm7`. Cửa `G` → `Csus4` vẫn là 0.50; nó không hát quãng 4 khi gốc Đô chưa được giữ. `rally` trưởng không dính ca Đô vì Đô và Fa còn được trừ 0.08, và Sol không có cửa sang Fa. Sus chỉ nghe khi gốc đó đang được giữ và phách mạnh là âm màu — khoản 0.70 lúc đó mới kéo giá xuống dưới F, kể cả ở `rally`. Ô đầu không phải pedal, uptrend hoặc downtrend, character không phải `selloff`, về F. Bonus chủ âm đầu câu (`PHRASE_TONIC_BONUS` 0.25) chỉ trao cho hợp âm ba/bảy chủ.

**`VillaDialect.bias`**, tất cả dưới 0.1, cộng thêm lên sàn 0.08 chứ không thay sàn đó, và chỉ khi một phách mạnh là âm màu. Gốc và quãng 5 không mua mức giảm. Nếu không, `calm` trừ 0.08 cho `Fsus2` xóa đúng sàn, Đô nằm trong cả `F` lẫn `Fsus2`, và ô thứ ba thành `Fsus2`. Thứ cũng vậy: hợp âm villa không lấy `minor_bias` của gốc (Đô là 0.00). Nếu lấy, `rally` trừ 0.04 cho sus4 khiến `Csus4` rẻ hơn `Cm` trên cùng một cửa. `calm` trừ 0.08 cho sus2 và add9; `volatile` trừ 0.08 cho 7sus4 và hợp âm trượt; `rally` trừ 0.04 cho sus4; `selloff` ở mode thứ trừ 0.08 cho sus của dialect và cho `Absus2`. Không bias nào bù được phạt phách mạnh 2.5. Mức `rally` −0.04 của sus4 cũng không tự giữ sus trước F: phần đó nằm ở khoản 0.70. Ô đầu bài, khoản bằng 0, nên 0.04 của F ở uptrend và downtrend vẫn rẻ hơn sàn 0.08 — trừ `selloff` và sideway, như mục trên.

Tỉa bè của các hình này nằm ở mục 5.3. Bè giữa của lớp Chord-melody và Pattern lấy âm màu đó, không đi tìm âm ba của một hợp âm sus.

---

## 4. Ba phong cách

### 4.0. Bản đồ nhịp điệu: meter, tempo và cảm giác nhịp theo khung

Guitar **không** mượn nguyên bản đồ nhịp của giao hưởng và không đứng yên ở 4/4. Nhưng `FormSpec` hiện chỉ mang **một meter cho cả chương** (`form.py::Meter`, `compose_meter` đặt một lần cho cả `_compose`), nên thay đổi nhịp điệu đi theo ba tầng, theo đúng khả năng của pipeline:

1. **Đổi meter giữa các chương** (tầng form): `span.py` thêm một nhánh guitar riêng *trong* cả ba hàm `month_specs`/`quarter_specs`/`year_specs` (không phải một hàm mới tên `guitar_specs`) thay vì rơi vào nhánh mặc định của giao hưởng. Cách đổi giữ nguyên số ô và BPM của từng chương nhưng **hoán đổi meter có cùng số móc đơn mỗi ô** (6/8 ↔ 3/4 đều 6 móc/ô), nên tổng số móc, thời lượng chương, khung warm-up (`frame_bars_for` cho 3/4 và 6/8 ở `1Y` đều là 3 ô, ở các span khác đều là 6 ô) và trần đồng hồ `47:21` giữ nguyên từng giây:

   | Khung | Chương | Meter giao hưởng hiện tại | Meter guitar | Cảm giác nhịp mới |
   |---|---|---|---|---|
   | `1M` | I (96 BPM) | 4/4 | 4/4 | Hành khúc/biến tấu |
   | `1M` | II (72 BPM) | 6/8 | **3/4** | Chương chậm thành nhịp ba hát kiểu waltz tang — đây là nhà của Élégiaque và chord-melody, xem mục 4.1/4.2 |
   | `1M` | III (120 BPM) | 3/4 | **6/8** | Scherzo thành hai phách lớn chấm dôi (tarantella/pastorale) — nhà của chạy dây và pattern cuộn |
   | `1M` | IV (96 BPM) | 4/4 | 4/4 | Finale, thêm nhóm lệch 3+3+2 ở cao trào |
   | `3M` | I / III | 4/4 | 4/4 | Như `1M` I/IV |
   | `3M` | II (60 BPM) | 6/8 | **3/4** | Như `1M` II nhưng chậm hơn |
   | `1Y` | Tháng mở mùa (100 BPM) | 4/4 | 4/4 | — |
   | `1Y` | Tháng giữa mùa (66 BPM) | 6/8 | **3/4** | Như chương chậm |
   | `1Y` | Tháng khép mùa (108 BPM) | 3/4 | **6/8** | Như scherzo |
   | `1Y` | Tháng 12 (96 BPM) | 4/4 | 4/4 | Finale |

   Vì chỉ hoán đổi meter cùng số móc, test đồng hồ hiện tại thêm một hàng `"guitar": (970.0, 1530.0, 2840.1)` bằng đúng giao hưởng. `swing_for("guitar", ...)` luôn `False` (guitar không swing; lệch nhịp đi bằng nhóm accent, mục dưới).

2. **Đổi cảm giác nhịp trong chương** (tầng nhóm phách): Trong cùng một meter, mỗi lớp chất liệu nhóm móc khác nhau — 4/4 có thể nghe thành hành khúc (nhấn 0, 4) hoặc thành lệch 3+3+2 (nhấn 0, 3, 6); 6/8 bình thường nhấn hai nhóm 3+3 (móc 0, 3), và khi cần căng thì đổi nhấn sang **2+2+2** (móc 0, 2, 4) — đó mới là hemiola trong 6/8, ba nhóm hai móc chồng lên hai phách chấm dôi; hemiola còn lại nằm ở 3/4 của lớp Pattern Villa (nhấn móc 0 và 3, mục 4.2). Luật nhấn 3+3+2 do **renderer guitar tự cài** (chỉ ở ô `mf/f` của character `volatile`, tối đa 2 ô liên tiếp): `build_groove` trong `groove.py` hiện chỉ đặt cờ `tresillo` cho `symphony` và `minimalist` và không có trần số ô liên tiếp, nên đọc `groove_at(bar)` sẽ không bao giờ tự cho ra tresillo cho guitar — không được viết như thể cơ chế đó sẵn có. Đây là thay đổi nhịp điệu thật ở tầng nghe, không cần đổi ký hiệu nhịp, và không đụng playhead.
3. **Đổi mật độ chia nhỏ** (tầng subdivision): Cùng một phách, Sor chia 2 (móc đơn), Villa chia 2 nhưng nhóm bất đối xứng, Barrios chia 4 (móc kép tremolo/chạy dây). Đây là tầng mà `divisions` của `Score` điều khiển.

Hai việc **không** làm trong đợt này, ghi rõ để không ai kỳ vọng: (a) đổi ký hiệu nhịp *giữa* một chương — `FormSpec`/`compose_meter`/`playback` đều giả định một meter mỗi chương, làm việc này là dự án riêng; (b) rubato/tempo trôi trong chương — `piece_seconds` tính thời lượng từ một `bpm` duy nhất, chèn `<sound tempo>` giữa bài sẽ lệch playhead và `mapDurationSec`. Nhịp điệu biểu cảm đi bằng ba tầng trên.

Tempo riêng theo phong cách chỉ áp cho `1D` (nơi mỗi variant đang có BPM riêng trong renderer). `1D` giữ 4/4 và khung 34 ô như các variant ensemble khác (khung này khóa theo `DAILY_ENSEMBLE_SPEC` và con trỏ chart), nên ở `1D` thay đổi nhịp điệu đi bằng tầng 2 và 3. `1W` giữ lưới 32 ô/phiên 4/4 ở 90 BPM (lưới này khóa theo phiên giao dịch), nhịp điệu đổi theo character từng phiên: `calm` = half-time (bass 2 phách), `rally` = hành khúc, `volatile` = nhóm 3+3+2, `selloff` = mẫu chấm dôi.

| Phong cách | BPM `1D` đề xuất | Lý do |
|---|---|---|
| Sor (`classic`) | 88 | Gần tempo giao hưởng 90, đủ chậm để câu cân đối nghe rõ |
| Villa-Lobos (`villa`) | 100 | Arpeggio cuộn cần đà; nhanh hơn Sor một bậc |
| Barrios (`barrios`) | 76 | Chuỗi tuần tự `p–a–m–i` ở 76 BPM ≈ 5 lần gảy/giây (mục 4.3.2), trong vùng chơi thật; nhanh hơn sẽ thành tiếng rè |

**Hệ quả bắt buộc cho các bảng pattern ở mục 4.1–4.3**: Mọi pattern phải được viết theo meter đang chạy, đọc từ `active_meter()` (`eighths_per_bar`, `strong_eighths`), không khóa cứng lưới 0–7 của 4/4. Mỗi lớp chất liệu có bảng riêng cho 4/4, 6/8 và 3/4 như dưới đây; test phải render đủ ba meter (mục 8).

**Band của câu (chốt cho mọi hàm chọn lớp khóa theo câu)**: `band_at` là hàm theo ô, nhưng `villa_layer`/`barrios_layer` khóa lớp theo từng câu. Band truyền vào hai hàm này là **band của ô chứa nốt đỉnh của câu** (ô apex trong `phrases`) — không phải ô đầu câu, không phải band mạnh nhất trong câu. Mọi test chọn lớp ở mục 8 phải dựng câu với apex đặt ở ô mang band cần kiểm tra, nếu không ca biên sẽ không tái lập được. `sor_layer` không nhận band nên không bị ảnh hưởng.

### 4.1. Phong cách cổ điển kiểu Sor (`classic`) — ba lớp chất liệu, không chỉ study

Chỉ dùng chất liệu study (giai điệu + arpeggio đều đặn) cho cả bài sẽ đơn điệu, nhất là ở bản dài. Sor có hai cực khác hẳn trong sáng tác lớn, và kế hoạch dùng cả ba lớp chất liệu này làm **chế độ nội bộ** của cùng một lựa chọn `classic` — người nghe vẫn chỉ chọn "Cổ điển · Sor", hệ thống tự chọn lớp chất liệu theo tính cách thị trường (`character`) và vai chương. Đây là cùng một nguyên tắc mà các variant khác đã dùng khi cho character điều khiển groove.

**Nghiên cứu cần làm trước khi code (Bước 0b ở mục 7)**: đọc tổng phổ (cả ba tác phẩm đều đã hết bản quyền, có trên IMSLP) và trích một "catalog chất liệu" — mỗi mục gồm nhịp điệu, cách bố trí ba bè, và điều kiện dữ liệu kích hoạt. Không sao chép giai điệu hay đoạn nhạc cụ thể nào của Sor; chỉ học ngữ pháp chất liệu.

| Lớp chất liệu | Tác phẩm nguồn | Đặc trưng cần trích ra | Kích hoạt khi |
|---|---|---|---|
| **Study** | Các study Op. 31/35, Op. 6 | Giai điệu hát trên arpeggio đều, câu 4–8 ô cân đối, nửa kết/toàn kết rõ | `calm`, hoặc mở đầu mỗi chương/bài (cho tai định vị đường giá trước khi chất liệu đậm vào) |
| **Grand Solo** | *Grand Solo* Op. 14 (giọng Rê trưởng): mở đầu kịch tính kiểu opera, chủ đề rồi **biến tấu** — cùng một khung giai điệu/hòa âm được trình bày lại với figuration dày dần, đoạn chạy bậc thang (scale run) lên đỉnh, hợp âm khối kiểu fanfare, điểm dừng kịch tính | Nguyên tắc biến tấu theo lần lặp; scale run nối lên nốt đỉnh câu; hợp âm khối 3 nốt ở phách mạnh đầu đoạn; khoảng lặng ngắn (1 móc) trước câu cao trào | `rally` và `volatile` ở chương nhanh (I, III, IV của `1M`, chương mở/khép của `3M`/`1Y`), **từ câu thứ hai trở đi** — đúng hàm `sor_layer` ở dưới. Câu lặp lại hay "nửa sau bài" **không** phải điều kiện bật lớp: chúng chỉ quyết định mức figuration tăng trong cơ chế biến tấu (câu `calm` lặp ở nửa sau vẫn là `study`) |
| **Élégiaque** | *Fantaisie élégiaque* Op. 59 — tác phẩm cuối đời của Sor, viết tưởng nhớ một người bạn qua đời: mở bằng hành khúc tang, giai điệu than thở nhiều appoggiatura, bass đi xuống từng bậc, đoạn lặng và cao trào bi tráng rồi lắng xuống | Bass hành khúc chấm dôi (dotted rhythm) viết theo từng meter; bass đi xuống liền bậc ở cuối câu (lament); appoggiatura thật ở phách mạnh — nốt ngoài hợp âm kề bậc với nốt dữ liệu, giải quyết vào đúng nốt dữ liệu ở móc kế tiếp (cơ chế 3 ở dưới, không phải tie); texture thưa hẳn, nhiều khoảng lặng hơn study | `selloff`; mọi chương chậm (II của `1M`/`3M`, tháng giữa mùa `1Y`) bất kể character; đoạn giữa mang cờ `trio` (scherzo, và tháng khép mùa `1Y`) khi mode là Thứ |

Hàm chọn lớp chất liệu đề xuất: `sor_layer(character, *, slow_movement: bool, section_kind: str, mode: str, trio: bool = False) -> Literal["study", "grand", "elegiaque"]`, với `slow_movement` suy từ BPM/meter của `FormSpec` như cách khung động đang suy (`bpm <= 72` là chương chậm), và `trio` **đọc thẳng từ `section.trio`** — cờ có sẵn trên `FormSection`, do `_with_trio` trong `span.py` gắn vào các section `phrase` có `regime_slot == 1`. Renderer không tự suy trio từ BPM hay vị trí section. Hai tham số `mode`/`trio` tồn tại vì hàng Élégiaque trong bảng trên có một kích hoạt mà chữ ký cũ không diễn đạt được: scherzo guitar là 6/8 ở 120 BPM — không chậm, nên đoạn giữa của nó ở mode Thứ với character `volatile`/`calm` sẽ trượt thành `grand`/`study` nếu hàm không thấy `mode` và `trio`. Phạm vi của luật trio (chốt, không để mỗi nơi hiểu một kiểu): luật áp cho **mọi section mang cờ `trio` ở mode Thứ** — tức đoạn giữa scherzo của `1M` *và* tháng khép mùa của `1Y` (6/8 ở 108 BPM theo bản đồ guitar, vốn cũng được `_with_trio` gắn cờ trong nhánh mặc định). `3M` không có chương scherzo và `quarter_specs` không bọc `_with_trio` ở movement nào, nên `3M` không có section trio nào và luật này không bao giờ kích hoạt ở đó — đừng đi tìm scherzo của `3M`. Tháng khép không phải scherzo về tên, nhưng section trio của nó đóng cùng vai đoạn giữa tương phản, nên đi cùng luật; ở mode Trưởng, section trio không kích hoạt Élégiaque và quay về luật character thường. Thứ tự ưu tiên, xét theo đúng thứ tự này, khóa theo từng câu (không đổi lớp giữa câu): (1) chương chậm, hoặc `selloff`, hoặc (`trio` và mode Thứ) → `elegiaque`; (2) `rally`/`volatile` ở chương nhanh, từ câu thứ hai trở đi → `grand`; (3) còn lại → `study`.

**Pattern theo thanh khoản của lớp Study, ô 4/4** (vị trí tính bằng móc đơn 0–7):

| Band | Bè Trầm | Bè Trung | Bè Cao |
|---|---|---|---|
| `p` | Gốc ở móc 0, ngân cả ô | Nghỉ, hoặc âm 3 ở móc 4 | Giai điệu nguyên trạng, nốt dài |
| `mp` | Gốc móc 0, quãng 5 móc 4 | Arpeggio lên 2 nốt: âm 3 móc 2, âm 5/7 móc 6 | Giai điệu nguyên trạng |
| `mf` | Gốc móc 0, quãng 5 móc 4 | Arpeggio 4 nốt (âm 3–5–7–5) ở móc 2, 3, 6, 7 | Thêm nốt điểm ở cuối câu đóng |
| `f` | Gốc móc 0, quãng 5 (gập vào dải Trầm) móc 4, gốc móc 6 | Arpeggio đều 4 móc lẻ, velocity +1 bậc | Accent ở nốt breakout/đỉnh, tenuto |

**Pattern của lớp Study ở 6/8 và 3/4** (6 móc/ô; 6/8 có hai nhóm ở móc 0 và 3, 3/4 có phách mạnh ở móc 0 và trọng số phụ ở móc 4 theo `METER_34`):

| Meter | Band | Bè Trầm | Bè Trung | Bè Cao |
|---|---|---|---|---|
| 6/8 | `p` | Gốc móc 0 ngân hết ô | Âm 3 ở móc 3 (đầu nhóm hai) hoặc nghỉ | Nguyên trạng |
| 6/8 | `mp` | Gốc móc 0, quãng 5 móc 3 | Âm hợp âm ở móc 1 và 4 | Nguyên trạng, nhấn đầu nhóm |
| 6/8 | `mf`/`f` | Gốc móc 0, quãng 5 móc 3 (`f` thêm gốc móc 5 làm nốt dẫn về ô sau) | Arpeggio đều móc 1, 2, 4, 5 | Accent ở nốt đầu nhóm trùng đỉnh/breakout |
| 3/4 | `p` | Gốc móc 0 ngân 4 móc, quãng 5 móc 4 | Nghỉ hoặc âm 3 ở móc 4 | Nguyên trạng |
| 3/4 | `mp` | Gốc móc 0, quãng 5 móc 4 | Âm hợp âm ở móc 2 và 5 | Nguyên trạng |
| 3/4 | `mf`/`f` | Gốc móc 0, quãng 5 móc 2, gốc/quãng 5 móc 4 | Arpeggio móc 1, 3, 5 | Accent ở móc 0; móc 4 chỉ nhấn khi trùng đỉnh câu |

**Chất liệu Grand Solo — ba cơ chế cụ thể**:
1. **Biến tấu theo lần lặp (cơ chế quan trọng nhất)**: Renderer giữ một mức figuration `level ∈ {0, 1, 2}` cho mỗi "họ câu". Hai câu thuộc cùng một họ khi **cả bốn** điều kiện sau cùng đúng: (a) cùng pitch-class gốc hợp âm ở ô mở đầu câu (`slots` của ô đó có cùng `root_step` + `alter`); (b) cùng dấu hướng nét (`sign(nốt cuối − nốt đầu)` của đường giai điệu đã nén bằng nhau); (c) cao độ đỉnh câu lệch nhau không quá 2 bậc thang; (d) độ dài câu lệch nhau không quá 4 móc đơn. Khi một câu mới cùng họ với câu liền trước trong cùng section (hoặc là câu đầu của section tái hiện có `regime_slot` trùng section trình bày), mức tăng một bậc thay vì lặp nguyên pattern: level 0 = pattern study, level 1 = arpeggio chạy đủ các móc yếu của ô, level 2 = thêm scale run và hợp âm khối đầu câu. Khung giai điệu (nốt phách mạnh) không đổi giữa các lần — người nghe nhận ra "cùng một ý" đang được trang trí thêm, đúng tinh thần theme-and-variations, và đường giá vẫn trung thực ở phách mạnh. Sang section mới không thuộc diện tái hiện thì mức đặt lại 0. Câu ở lớp `grand` mà không cùng họ với câu liền trước chạy ở level 0 (pattern study cộng hợp âm khối/fanfare theo cơ chế 3) — lớp được bật bởi character và vị trí câu, còn "họ" chỉ là đồng hồ đo mức biến tấu, không phải công tắc bật lớp.
2. **Scale run lên đỉnh**: Ở câu có `phrase.rise >= MIN_RISE` và band `mf/f`, hai móc ngay trước nốt đỉnh câu được thay bằng bậc thang liền bậc đi lên từ nốt giai điệu trước đó tới nốt đỉnh (chỉ dùng âm trong thang/hợp âm, không bịa nốt ngoài dữ liệu ở phách mạnh — nốt chạy nằm ở phách yếu). Cùng với appoggiatura của Élégiaque dưới đây, đây là hai chỗ duy nhất phong cách Sor cho phép nốt không trực tiếp từ giá, và cả hai đều bị khóa bằng test (nốt đích/nốt giải quyết phải là nốt dữ liệu).
3. **Fanfare và điểm dừng**: Đầu section ở band `f`: ô đầu đánh hợp âm khối 3 nốt (Trầm + Trung + Cao cùng lúc, đúng trần 3 bè) thay vì arpeggio; trước câu cao trào nhất của section (câu chứa đỉnh cao nhất), cho phép lặng 1 móc ở cả ba bè (caesura nhỏ) nếu câu trước đó đóng — tạo hơi thở kịch tính kiểu phần mở đầu của *Grand Solo*.

**Chất liệu Élégiaque — ba cơ chế cụ thể**:
1. **Bass hành khúc tang, theo meter** (dấu hiệu tang phải khác hẳn pattern thường ngay trong meter của chương chậm — mà theo mục 4.0, nhà của lớp này là 3/4, không phải 6/8):
   - **4/4**: Bè Trầm đi mẫu đen chấm + móc đơn ở mỗi nửa ô: móc 0 dài 3, móc 3 ngắn 1 (nốt đi xuống liền bậc), móc 4 dài 3, móc 7 ngắn 1.
   - **3/4** (chương chậm): Mẫu chấm dôi đặt ở phách 1: móc 0 dài 3, móc 3 ngắn 1 là nốt đi xuống liền bậc, móc 4 dài 2 là nốt than tiếp theo. Sang ô kết câu, bass ngân móc 0 hết ô. Mẫu này khác pattern Study 3/4 ở chỗ phách 2 bị "nuốt" vào nốt chấm dôi — đó chính là nhịp hành khúc nghe được.
   - **6/8** (gặp ở mọi đoạn 6/8 mà lớp Élégiaque chạy — section `trio` mode Thứ *và* cả chương 6/8 khi character là `selloff`, vì ưu tiên (1) của `sor_layer` đưa `selloff` vào lớp này ở mọi section, không chỉ trio; scherzo và tháng khép `1Y` đều là 6/8 nên ca `selloff` phủ cả chương): Không dùng mẫu chấm dôi của nhóm (trùng với chính nhóm 6/8 nên không còn là dấu hiệu). Thay vào đó chia nhỏ mỗi nhóm: móc 0 dài 2, móc 2 ngắn 1 (nốt đi xuống), móc 3 dài 2, móc 5 ngắn 1 — nhịp bị "kéo lê" trong từng nhóm, cộng bass đi xuống ở dưới.
2. **Bass than đi xuống**: Ở 2 ô cuối câu đóng trong mode Thứ, bè Trầm ưu tiên đi xuống liền bậc theo thang (gốc → bậc 7 thang → bậc 6 → quãng 5, mọi nốt gập vào dải Trầm) thay vì nhảy gốc–quãng 5, khi hợp âm cho phép; đây là dấu hiệu nghe rõ nhất của lớp này.
3. **Thưa, lặng và appoggiatura thật**: Mật độ bè Trung giảm một bậc so với bảng Study (đang `mf` viết như `mp`), hairpin dài hơn (theo cả câu thay vì nửa câu), và nốt cuối câu ngân hết phần còn lại thay vì fill. **Appoggiatura** phải là nốt tựa thật, không phải tie: ở lớp này, khi nốt giai điệu dữ liệu ở phách mạnh được giữ ≥ 2 móc và nốt dữ liệu kế tiếp thấp/cao hơn đúng 1 bậc thang, cho phép thay móc đầu tiên của nốt phách mạnh bằng một **nốt ngoài hợp âm** nằm cách nốt giải quyết (chính nốt dữ liệu đó) đúng 1 bậc thang theo hướng ngược với hướng giải quyết, đánh ở phách mạnh với accent, rồi giải quyết vào nốt dữ liệu ở móc ngay sau. Tối đa 1 appoggiatura mỗi câu; nốt tựa lấy từ thang của mode (không chromatic), và vì nó chiếm phách mạnh nên đây là ngoại lệ có chủ đích với quy tắc "phách mạnh là âm hợp âm" của pipeline — chỉ bật trong lớp Élégiaque và có test khóa nốt giải quyết.

**Quy tắc chung của cả ba lớp**:
- Dialect hòa âm của Sor là `COMMON` (mục 3.4): hòa âm giữ dạng ba/âm bảy nguyên bản từ `slots`, tỉa xuống tối đa 3 nốt theo mục 5.3; ưu tiên hợp âm thuận thang, hợp âm mượn chỉ ở vai trò hiện tại của chúng (đi qua, màu downtrend).
- Cuối mỗi câu đóng (`phrase.closes`): bass kết câu đi theo `slots`, không tự chế — chỉ khi hợp âm của ô cuối câu trong `slots` đã là V (hoặc V7 tỉa bè) thì bass mới là bậc V và ô đầu câu sau về I/i như thường lệ; nếu slot của ô đó không phải V, giữ bass đúng gốc của slot. Không bao giờ viết bass bậc V dưới một ký hiệu hợp âm khác: bản nhạc sẽ hiện một hợp âm và nghe một bass khác. (Đổi luôn ký hiệu hợp âm theo bass là phương án bị loại — ký hiệu phải khớp Viterbi `slots` mà mọi tầng khác đang đọc.) Bè Trung chạy fill arpeggio lên 3 nốt giống `fills()` hiện tại nhưng nằm trong âm vực bè Trung (ở lớp Élégiaque, fill này bị tắt — kết câu bằng lặng).
- Slur theo câu, hairpin về đỉnh câu, dynamics theo `band_at` — tái dùng nguyên `phrasing.py`.
- Không chromatic approach tự do, không nhịp lệch (syncopation) ngoài accent sẵn có của `accent_of` và các cơ chế đã liệt kê. Tính "cổ điển" nằm ở kỷ luật này, còn sức nặng biểu cảm lấy từ chọn lớp chất liệu, biến tấu và khoảng lặng — không phải từ thêm nốt.

### 4.2. Phong cách hiện đại kiểu Villa-Lobos (`villa`)

**Thẩm mỹ tham chiếu**: Étude No. 1 của Villa-Lobos là một mẫu tay phải lặp nguyên vẹn qua từng ô trong khi tay trái trượt hợp âm — gồm cả hợp âm giảm và chromatic. Étude No. 2 mở arpeggio ra khoảng rất rộng, No. 7 chạy bậc thang nhanh. Nhưng nếu chỉ có arpeggio thì phong cách này cũng đơn điệu như Sor chỉ-study — vì vậy phải dùng thêm **Étude No. 11**, bản étude tương phản nhất trong bộ 12: đoạn mở chậm, hát, viết kiểu **giai điệu nằm trên hợp âm** (chord-melody — giai điệu là nốt cao nhất của các hợp âm được đánh cùng lúc, bè dưới đi những bước tay trái rộng), tương phản với đoạn nhanh hợp âm dồn dập, mạnh. No. 11 cho phong cách này lớp chất liệu chậm/biểu cảm mà No. 1/2 không có, và rất hợp với trần 3 nốt của ta vì chord-melody của Villa-Lobos thường chỉ cần đúng 3 nốt một lúc là đủ nghe ra. Chất hòa âm — sus, add9 không kèm âm 7, và trượt cùng một hình — do dialect mục 3.4 chọn. Đổi pattern gảy trên catalog hợp âm ba không ra chất này.

**Nghiên cứu cần làm trước khi code (Bước 0b ở mục 7)**: đọc tổng phổ các Étude No. 1, 2, 7, 11 (bộ 12 études đã hết bản quyền ở nhiều nơi nhưng bản biên tập còn có thể có bản quyền — chỉ trích ngữ pháp chất liệu, không chép đoạn nhạc) và trích catalog: mẫu ngón tay phải của No. 1, khoảng arpeggio của No. 2, kiểu chạy bậc thang của No. 7, và ở No. 11: nhịp điệu đánh hợp âm của đoạn chậm, cách giai điệu ngồi trên hợp âm, và cách đoạn nhanh dồn hợp âm theo nhóm.

Ba lớp chất liệu nội bộ, chọn bằng hàm `villa_layer(character, band, *, slow_movement: bool, phrase)`. Khi nhiều điều kiện cùng đúng, xét theo **thứ tự ưu tiên** này, khóa theo từng câu: (1) chương chậm + band `f` + `volatile` + câu có breakout → **Bậc thang** cho riêng câu đó (cao trào của chương chậm), câu sau quay lại Chord-melody; (2) chương chậm (mọi trường hợp còn lại), hoặc chương nhanh với band `p`/`calm` → **Chord-melody**; (3) chương nhanh + `volatile` + band `f` + `phrase.rise >= MIN_RISE` → **Bậc thang**; (4) còn lại → **Pattern**.

| Lớp chất liệu | Nguồn | Vai |
|---|---|---|
| **Pattern** (arpeggio lặp) | Étude No. 1/2 | Mặc định ở chương nhanh, band `mp–f` |
| **Chord-melody** | Étude No. 11 | Lớp hát: chương chậm và chỗ thưa của chương nhanh |
| **Bậc thang** (scale/arpeggio rộng) | Étude No. 7/2 | Chen đoạn chạy liền bậc 4–6 móc thay một phần arpeggio ở câu căng |

**Đường giá nằm ở đâu trong lớp Pattern (chốt, áp cho mọi band)**: Bè Cao luôn mang đường giai điệu giá đã nén như các phong cách khác, đánh trên lưới móc đơn của chính nó (nốt giữ nguyên thời lượng theo câu, không bị pattern nuốt). Vòng arpeggio ở bảng dưới chỉ gồm bè Trầm và bè Trung/Trung-cao chạy *bên dưới* giai điệu: nốt "Trung cao" là âm hợp âm cao nhất còn thấp hơn nốt giai điệu đang vang ít nhất 3 nửa cung; ở móc nào giai điệu tự đánh, Trung cao hoặc nghỉ hoặc chọn âm hợp âm thấp hơn tiếp theo, tuyệt đối không trùng cao độ và không cao hơn giai điệu. Velocity bè Cao hơn velocity vòng arpeggio 8–12 đơn vị để nốt giá luôn nổi nhất — đây là điều kiện của checklist nghe ở mục 8.

**Pattern theo thanh khoản của lớp Pattern, ô 4/4** (vòng dưới giai điệu; số là móc đơn):

| Band | Cách viết |
|---|---|
| `p` | Thưa kiểu Prélude: Trầm đầu ô + giai điệu, bè Trung chỉ điểm 1 nốt đầu ô |
| `mp` | Nửa mẫu arpeggio: 4 móc đầu ô theo vòng Trầm → Trung → Trung cao → Trung |
| `mf` | Mẫu arpeggio đầy 8 móc lặp cả ô: Trầm(0) → Trung(1) → Trung(2) → Trung cao(3) → Trầm quãng 5(4) → Trung(5) → Trung cao(6) → Trung(7) |
| `f` | Mẫu đầy + trượt chromatic: nốt bass cuối ô (móc 7) là nốt dẫn bán cung về gốc ô sau (lên hoặc xuống tùy hướng), và cứ 2 ô thì mẫu dịch lên một bậc hợp âm (sequence) nếu `slots` cho phép |

**Lớp Pattern ở 6/8 và 3/4**: 6/8 chạy đúng một vòng mỗi ô — Trầm(0) → Trung(1) → Trung cao(2) → Trầm quãng 5(3) → Trung(4) → Trung cao(5) — nhấn đầu hai nhóm (móc 0 và 3). 3/4 chạy vòng Trầm(0) → Trung(1) → Trung cao(2) → Trầm(3) → Trung(4) → Trung cao(5), và ở band `f` nhấn móc 0 và 3 — hai nhóm ba móc chồng lên ba phách đen, đó là hemiola thật của phong cách này. Band `p`/`mp` ở hai meter này rút vòng xuống còn móc 0, 2, 4 (`mp` thêm móc đầu nhóm/phách cuối).

**Quy tắc viết**:
- Hòa âm là `VillaDialect` (mục 3.4), đã chọn xong trong `plan_slots`. Bè Trung lấy âm màu của hợp âm đó: quãng 2, quãng 4, b7, hoặc quãng 9 của add9. Không gọi `jazz_chord` trên slot villa — hàm đó đổi hợp âm thành dạng chín theo gốc và xóa sus. Không nới `BORROWED` cho villa; màu chromatic của ông nằm ở hai hợp âm trượt của dialect.
- Campanella có giới hạn: cho phép nốt bè Trung ngân chồng qua nốt Cao kế tiếp (duration kéo dài thêm 1 móc) khi hai nốt khác dây theo mô hình dây ở mục 5.2 — tạo tiếng vang chồng đặc trưng mà vẫn tối đa ba bè logic.
- Accent theo nhóm bất đối xứng ở `f` (nhấn móc 0, 3, 6) thay vì đều phách — khác biệt nghe rõ nhất so với Sor.
- Câu chậm (chương II của `1M/3M`, tháng giữa mùa `1Y`): giảm một bậc mật độ (đang `mf` viết như `mp`) để giữ chất hát — trừ khi lớp Chord-melody đang chạy, vì lớp đó có quy tắc riêng dưới đây.

**Lớp Chord-melody kiểu Étude No. 11 — quy tắc riêng**:
- Giai điệu vẫn là đường giá ở bè Cao, nhưng ở phách mạnh, nốt Cao được đánh **cùng lúc** với bè Trầm (gốc) và một nốt bè Trung thành hợp âm khối đúng 3 nốt — đây là ngoại lệ có chủ đích của quy tắc "arpeggio là chính", và là dấu hiệu nhận diện của lớp này. Nốt Trung là âm 3 hoặc âm 7 với hợp âm ba/bảy, và là quãng 2, quãng 4 hoặc b7 khi hợp âm có `quality_group == "suspended"` (mục 3.4, 5.3). Lưới cú khối theo meter: 4/4 ở móc 0 và 4; 6/8 ở đầu mỗi nhóm (móc 0 và 3); **3/4 — nhà chính của lớp này ở chương chậm — chỉ ở móc 0**, vì `METER_34.strong_eighths` chỉ có móc 0. Móc 4 của 3/4 (trọng số phụ 0.8 trong `extra_weights`, không phải phách mạnh) chỉ được thêm **một** cú khối tăng cường ở ô chứa đỉnh câu hoặc ô kết câu, không thành lưới hai cú đều khắp lớp — viết khối ở cả 0 và 4 mọi ô 3/4 sẽ biến chương chậm thành nhịp hai phách và xóa dấu hiệu nhịp ba mà mục 4.0 cố tạo.
- Giữa các phách mạnh, bè Trung chỉ gảy 0–2 nốt nối rất thưa (ưu tiên ngân hợp âm vừa đánh), để cảm giác là hợp âm hát chứ không phải arpeggio. Bass được phép nhảy rộng (bước tay trái rộng là chất của No. 11) theo profile `villa_chord` ở mục 5.4, nhưng vẫn trong âm vực Trầm và phải qua kiểm tra gán dây.
- Nhịp đánh hợp âm đi theo câu, nhưng **không được phá lưới cú khối của meter** ở gạch trên: luật "dồn dần" dưới đây chỉ áp trong 4/4. Ở 4/4, câu đang lên thì các cú đánh hợp âm dồn dần (cách nhau 4 móc → 2 móc), câu đóng thì giãn ra và cú cuối ngân hết phần còn lại của ô; ở đoạn cao trào của section (câu chứa đỉnh cao nhất, band `f`), cho phép 2–3 cú hợp âm khối liên tiếp cách nhau 2 móc — mô phỏng đoạn nhanh dồn dập của No. 11 mà vẫn không vượt 3 nốt/lúc. Ở **6/8**, cú khối chỉ rơi vào đầu nhóm (móc 0 và 3): "dồn" nghĩa là đi từ một đầu nhóm mỗi ô lên cả hai đầu nhóm, và cao trào tăng bằng velocity/thời lượng ngân chứ không chèn cú ở móc 2 hay 4. Ở **3/4**, cú khối chỉ ở móc 0 (cộng cú tăng cường móc 4 ở ô đỉnh/kết): "dồn" diễn ra *giữa các ô* — từ khối cách 2 ô thành mỗi ô một khối khi câu lên — và cao trào chỉ được dùng cú móc 4 tăng cường đó, không có chuỗi khối cách nhau 2 móc trong ô 3/4. Viết khối ở móc 2 của ô 3/4, hay ở móc 2/4 của ô 6/8, là lỗi lưới chứ không phải biến tấu.
- Dynamics của lớp này đi theo cả câu (một hairpin dài) thay vì theo ô, và velocity cú đánh hợp âm cao hơn nốt nối 8–12 đơn vị để giai điệu trên hợp âm nổi rõ.

### 4.3. Phong cách tự do kiểu Barrios (`barrios`) — tremolo là trung tâm, *La Catedral* là khung

Chỉ tremolo suốt bài vừa mệt tai vừa phí mất Barrios. *La Catedral* — tác phẩm nổi tiếng nhất của ông, lấy cảm hứng từ tiếng chuông và không gian nhà thờ — tự nó đã có một cung hình ba phần rất hợp để tổ chức một bài sonify: **Preludio Saudade** (mở đầu mơ, motif chuông bằng harmonics trên nền arpeggio), **Andante Religioso** (hợp âm hát chậm như thánh ca), **Allegro Solemne** (chạy dây nhanh liên tục, virtuoso). Phong cách `barrios` dùng cung hình đó làm khung, và đặt tremolo của *El Último Trémolo*/*Sueño en la Floresta* ở giữa làm chất liệu hát chính. Người nghe vẫn chỉ chọn một lựa chọn `barrios`; hệ thống chọn lớp chất liệu theo vị trí trong bài, tính cách thị trường và thanh khoản. Trong phạm vi file này, dialect hòa âm của Barrios là `COMMON` (mục 3.4), cùng catalog với Sor. Dialect riêng và lớp tiết tấu choro đã chốt ở [`docs/sonify-barrios-harmony.md`](./sonify-barrios-harmony.md): Pha 1 đăng ký `BarriosDialect` vào `DIALECTS` sau Bước 4. Vòng chọn hợp âm giữ nguyên, trừ điều kiện một ô `"augmented-sixth"` trong `form.py`. Bước 4 của file này vẫn viết bốn lớp trên catalog chung.

**Nghiên cứu cần làm trước khi code (Bước 0b ở mục 7)**: đọc cả ba phần của *La Catedral* (tác phẩm đã hết bản quyền; lưu ý Preludio được Barrios bổ sung sau, nên các bản biên tập có thể khác nhau đôi chút) và trích catalog riêng cho Barrios: motif chuông của Preludio (nhịp và khoảng cách các nốt chuông, cách arpeggio đệm chảy bên dưới), nhịp hợp âm thánh ca của Andante, và ở Allegro Solemne: độ dài một đoạn chạy dây (thường gom theo nhóm móc kép), cách chạy lên/xuống đổi hướng, và cách đoạn chạy nối vào nốt đích ở phách mạnh. Chỉ học ngữ pháp, không chép đoạn nhạc.

Bốn lớp chất liệu nội bộ, chọn bằng hàm `barrios_layer(section_kind, character, band, *, phrase, bpm)`. Khi nhiều điều kiện cùng đúng, xét theo **thứ tự ưu tiên** này: (1) ô thuộc khung mở — `intro` ở bản ngày, `warmup` ở bản dài (xem quy ước tên khung ở mục 6.2) — hoặc câu đầu của chương → **Preludio**; (2) câu thỏa điều kiện Chạy dây (dưới đây) và còn ngân sách chạy của section → **Chạy dây** cho đoạn/câu đó — *ngoại lệ ở chương chậm*: Chạy dây chỉ thắng Tremolo khi band `f` **và** có breakout **và** `bpm <= 84`, còn lại chương chậm luôn là Tremolo/Thánh ca; (3) chương chậm: **Tremolo**, nhưng sau 2 câu tremolo liên tiếp thì 1 câu **Thánh ca**; (4) câu giai điệu giữ ≥ 2 phách ở band `mp–f` → **Tremolo**; (5) `calm` ở ô chuyển section → **Thánh ca**; (6) còn lại → arpeggio/nốt đơn thưa kiểu Preludio rút gọn. Lớp khóa theo từng câu; riêng Chạy dây xuống kết câu và Preludio được phép chiếm một *đoạn* trong câu (2 phách cuối / câu đầu) mà không đổi lớp của cả câu.

| Lớp chất liệu | Nguồn | Kích hoạt khi |
|---|---|---|
| **Preludio** (chuông + arpeggio mơ) | *La Catedral* — Preludio Saudade | Ô khung mở (`intro` ở `1D`, `warmup` ở bản dài) và câu đầu tiên của bài/chương; câu mở đầu một section mới sau điểm lặng; phiên `calm` mở đầu ở band `p` |
| **Tremolo** (hát ngân) | *El Último Trémolo*, *Sueño en la Floresta* | Thân bài: câu giai điệu giữ nốt dài, chương chậm, đoạn giá đi ngang cần giai điệu treo |
| **Chạy dây** (runs) | *La Catedral* — Allegro Solemne | Đỉnh câu và câu `volatile` band `mf/f`; nối lên nốt breakout; 1–2 ô trước kết câu lớn; cao trào của section |
| **Thánh ca** (chord chậm) — lớp phụ | *La Catedral* — Andante Religioso | Ô chuyển giữa hai section khi cần "đổi không khí" mà chưa vào cao trào; câu `calm` ở chương chậm mà tremolo đã chạy liên tục 2 câu trước (luân phiên để nghỉ tai) |

**Đơn vị "phách" trong toàn bộ mục 4.3** (chốt để các luật thời lượng viết test được): một phách là một đơn vị đen — đúng `NoteEvent.beat` — bằng 2 móc đơn hoặc 4 móc kép, ở cả 4/4, 3/4 và 6/8. Ở 6/8, một phách như vậy là nửa nhóm chấm dôi; cách gom tremolo theo phách chấm dôi ở mục 4.3.2 (1 cú ngón cái + 5 lần lặp) chỉ là cách gom ngón trong một nhóm, không phải đơn vị đo. Mọi luật dùng chữ "phách" trong phong cách này — giai điệu giữ ≥ 2 phách mới bật tremolo, tắt tremolo ở 2 phách cuối câu (= 8 móc kép), nốt chuông cách nhau 2–4 phách, đoạn chạy ở 2 phách cuối câu — đều đo bằng đơn vị đen này.

#### 4.3.1. Lớp Preludio — motif chuông ở đầu bài

- **Motif chuông**: Bè Cao đánh những nốt rất cao, thưa và ngân dài (ưu tiên 76–83, tức vùng đỉnh của âm vực guitar ở mục 3.1), mỗi nốt cách nhau 2–4 phách, velocity nhẹ hơn giai điệu thường 6–10 đơn vị nhưng tenuto và để ngân chồng qua bè Trung (campanella, chỉ khi mô hình dây mục 5.2 gán được khác dây). **Cao độ nốt chuông lấy từ dữ liệu, không bịa**: pitch-class là của nốt đỉnh trong câu mở đầu (hoặc âm hợp âm cao nhất của ô nếu câu chưa có đỉnh), đặt ở quãng tám cao nhất mà cao độ vang còn ≤ 83 và gán được trên dây 1/2 khác dây với nốt Trung đang vang; nếu pitch-class đó không có đại diện nào trong 76–83, lấy bậc thang gần nhất trong cửa sổ. Tính theo số viết, cửa sổ chuông là [`76 − semitones`, `guitar_ceiling`] đọc từ các biên ở mục 3.3. Đây là cách gợi tiếng chuông nhà thờ của Preludio mà **chưa cần harmonics thật**: harmonics tự nhiên trên guitar và việc MuseSounds `Acoustic Nylon` có hỗ trợ articulation harmonics qua MusicXML hay không phải kiểm chứng riêng ở Bước 0 bằng một nốt `<harmonic>` thử; nếu sample không đáp ứng, giữ cách gợi bằng nốt cao ngân chồng này và không xuất ký hiệu harmonic giả trên bản nhạc.
- **Đệm bên dưới**: Bè Trung arpeggio chảy đều móc đơn theo vòng âm hợp âm (gốc của vòng lấy từ `slots` như lớp Pattern của Villa nhưng chậm và nhẹ hơn, velocity −8), bè Trầm chỉ đánh gốc ở đầu mỗi 2 ô. Giai điệu giá ở những ô này vẫn nằm ở bè Cao khi nó không trùng nốt chuông: nốt chuông chỉ chen vào ở đầu câu và ở khoảng nghỉ của giai điệu (giai điệu nghỉ ≥ 2 móc), không đè lên nốt giá ở phách mạnh.
- **Ngân sách chuông (hai đơn vị khác nhau, không trộn)**: (a) *Số nốt*: tối đa 1 nốt chuông mỗi 2 ô. (b) *Số móc đơn điểm cao*: tổng thời lượng các nốt chuông (quy ra móc đơn, nốt ngân bao lâu tính bấy nhiêu) không vượt `bell_budget(rel_span, cap)` của `phrasing.py` — hàm này trả **số móc đơn**, bằng 0 khi biên độ phiên ≤ 0.5%. Giá trị `cap` do `_compose` truyền qua `bell_caps` và khác nhau theo khung, không được gộp làm một con số: ở `1D`, `form is None` nên cap là `None` và hàm dùng mặc định 36 móc; ở bản dài, cap của mỗi section là `round(0.15 × số móc của section)` và có thể **lớn hơn 36** ở section dài. Hệ quả phải ghi rõ: phiên phẳng (ngân sách 0) thì Preludio **không có nốt chuông nào** — lớp vẫn chạy bằng arpeggio mơ và giai điệu thưa, chuông chỉ xuất hiện khi phiên có biên độ thật, đúng như Preludio chỉ gợi chuông xa.
- Lớp này **chỉ ở đầu bài/chương và đầu section**; vào câu thứ hai của section là chuyển sang Tremolo hoặc Thánh ca. Preludio quay lại ở đầu chương sau của bản dài (mỗi chương là một lần "vào nhà thờ" mới), không quay lại giữa chương trừ sau một caesura lớn.

#### 4.3.2. Lớp Tremolo — chất liệu hát chính

**Cấu trúc một phách tremolo — khóa kiểu tuần tự `p–a–m–i`** (nhịp 4/4, `divisions = 4`): Mỗi phách đen có 4 móc kép và chúng được dùng **tuần tự, không chồng**: móc kép 0 là cú ngón cái (`p`) — nốt Trầm, hoặc nốt Trung thế chỗ ở riêng phách đổi hợp âm theo ngoại lệ ngay dưới đây (ở phách không có nốt bass theo pattern thì móc này nghỉ hoặc là nốt Trầm ngân tiếp; tuyệt đối không phải nốt giai điệu), ba móc kép 1–3 là cùng một nốt giai điệu do `a–m–i` lặp lại. Ở 76 BPM, một phách có 4 lần gảy ≈ 5 lần gảy/giây — khớp con số này chỉ với kiểu tuần tự. **Bè Trung không có nốt đánh mới nào trong một phách tremolo, trừ một ngoại lệ duy nhất**: âm hòa âm của bè Trung mặc định là nốt ngân từ cú đánh ở đầu câu/đầu ô trước khi tremolo vào (hoặc ở phách nghỉ tremolo), kéo duration qua các phách tremolo; nhưng khi hợp âm đổi mà tremolo đang chạy, bè Trung được đánh một nốt mới ở móc kép 0 của phách đầu ô mới *thay cho* nốt Trầm của phách đó (ngón cái đánh một nốt một lúc — phách đó không có bass riêng, và móc kép 0 đó vẫn chỉ có đúng một nốt đánh). Ngoại lệ này là một phần của định nghĩa tremolo, và test ở mục 8 phải chừa đúng chỗ này thay vì cấm tuyệt đối. Giai điệu chỉ đổi cao độ trên lưới móc đơn của dữ liệu (mỗi 2 móc kép), không đổi giữa chừng — dữ liệu giá vẫn là nguồn nhịp điệu chính, tremolo chỉ là lớp ngân. Ở 6/8, một phách lớn (đen chấm = 6 móc kép) đi: móc 0 = ngón cái, móc 1–5 = giai điệu lặp theo vòng `a–m–i–a–m`; ở 3/4 áp dụng mẫu 4/4 cho từng phách đen. Đây là lưới đầy, cho chương có tempo ≤ 100. Tempo trên 100 thay cả lưới này bằng lưới giảm ở mục 4.3.4; `p–a–m–i` không chạy trong các chương đó.

**Khi nào bật tremolo** (tránh bật suốt bài gây mệt tai):

| Điều kiện | Cách viết |
|---|---|
| Mở bài/khung mở (`intro`/`warmup`) | Lớp Preludio (mục 4.3.1), không tremolo |
| Thân bài, band `mp` | Tremolo ở câu có nốt giai điệu giữ ≥ 2 phách; câu chạy nhanh (nốt đổi từng móc đơn) nhường cho lớp Chạy dây hoặc arpeggio thường |
| Thân bài, band `mf`/`f` nhưng câu êm | Tremolo liên tục cả câu; bass thêm quãng 5 ở phách 3 |
| Cuối câu đóng | Tắt tremolo ở 2 phách cuối: chuyển sang arpeggio kết câu, hoặc một đoạn chạy dây đi xuống ngắn (mục 4.3.3) rồi nốt cuối ngân dài, tenuto |
| Chương chậm | Tremolo là mặc định (đây là "sân nhà" của phong cách này), bass thưa 1 nốt/ô; sau mỗi 2 câu tremolo liên tiếp, chèn 1 câu Thánh ca để nghỉ tai |

#### 4.3.3. Lớp Chạy dây — những đoạn chạy nhanh kiểu Allegro Solemne

"Chạy dây" là những đoạn bậc thang/arpeggio rất nhanh chạy dọc cần đàn, tạo cảm giác dòng nước xiết ở đoạn nhanh của *La Catedral*. Đây cũng là lớp tạo tương phản mạnh nhất với tremolo (một bên là một nốt lặp, một bên là nhiều nốt chạy), nên nó phải hiếm và có đích đến rõ.

Ba dạng chạy, tất cả đều trên lưới móc kép (`divisions = 4`, nhóm 4 móc kép mỗi phách):

| Dạng | Hình dạng | Kích hoạt khi |
|---|---|---|
| **Chạy lên đỉnh** | 4–8 móc kép liền bậc đi lên (âm thang + âm hợp âm), bắt đầu từ nốt giai điệu hiện tại hoặc thấp hơn nó 3–5 bậc, kết thúc **đúng** vào nốt đỉnh câu/breakout ở phách mạnh kế tiếp | Câu có `phrase.rise >= MIN_RISE`, band `mf/f`, nốt đỉnh là breakout hoặc đỉnh cao nhất section |
| **Chạy xuống kết câu** | 4–6 móc kép liền bậc đi xuống từ nốt đỉnh/nốt cuối câu về nốt kết (cadence) hoặc về gốc hợp âm ô sau | 2 phách cuối câu đóng, thay cho arpeggio kết câu thường; đặc biệt sau một câu tremolo dài |
| **Chạy liên tục (perpetual)** | Cả 1 ô (tối đa 2 ô liên tiếp) chạy móc kép theo vòng bậc thang lên–xuống trong bè Cao, bè Trầm vẫn đánh gốc ở phách 1 và 3, bè Trung nghỉ | Ô `volatile` band `f` mà giai điệu giá đứng yên ≥ 1 ô (giá phẳng nhưng thanh khoản nổ — chạy dây diễn tả năng lượng đó thay vì bắt giai điệu bịa nốt mới) |

**Ràng buộc trung thực dữ liệu (quan trọng nhất của lớp này)**:
- Đoạn chạy **chiếm bè Cao một mình** trong lúc nó chạy: không có một nốt giai điệu giữ song song bên trên, và bè Trung nghỉ (chỉ bè Trầm được đánh ở phách). Với dạng chạy lên đỉnh và chạy xuống kết câu, nốt ở mọi vị trí dữ liệu (phách mạnh và móc đơn đầu mỗi nửa phách) vẫn là nốt giá/hợp âm như pipeline hiện tại; nốt chạy chỉ nằm ở các móc kép còn lại giữa hai mốc dữ liệu — chạy dây là *trang trí giữa các mốc dữ liệu*, không bao giờ thay mốc dữ liệu, cùng nguyên tắc với scale run của lớp Grand Solo (mục 4.1) nhưng dày hơn và dài hơn. **Dạng perpetual là ngoại lệ có tên**: trong một phách 4 móc kép, móc kép 2 đồng thời là mốc móc đơn giữa phách, nhưng đoạn chạy phải rời nốt đang giữ mới thành chạy — nên ở dạng này, mốc dữ liệu chỉ neo ở móc kép 0 của mỗi phách (nốt giai điệu đang giữ), còn móc kép 2 là nốt chạy; đoạn chạy đi ra và quay về đúng nốt giữ trong cùng phách. Không được vừa đòi perpetual đứng yên ở móc kép 2 vừa đòi nó chạy.
- **Hai đầu đoạn chạy không đối xứng**: Nốt **đích** (cuối đoạn) phải trùng đúng nốt dữ liệu ở mốc kế tiếp (nốt đỉnh, nốt kết câu, hoặc nốt giá ở phách mạnh sau). Nốt **đầu** được phép là nốt thang nằm thấp hơn (chạy lên) hoặc cao hơn (chạy xuống) nốt giai điệu gần nhất 3–5 bậc thang — đó là nốt "lấy đà", không cần trùng dữ liệu, nhưng phải thuộc thang của mode. Riêng perpetual: nốt ở móc kép 0 của mỗi phách phải trùng nốt giai điệu đang giữ, đoạn chạy đi ra và quay về nốt đó trong cùng phách.
- Âm chạy lấy từ thang của mode đang chạy (Trưởng/Thứ tự nhiên, âm dẫn nâng ở ô hợp âm V như quy tắc hiện tại) và ưu tiên âm hợp âm ở các móc kép đầu nhóm 4; nốt chromatic chỉ cho phép ở 1 móc kép ngay trước nốt đích (nốt dẫn bán cung kiểu Barrios), tối đa 1 nốt chromatic mỗi đoạn chạy.
- Mỗi đoạn chạy dài 4–8 móc kép (riêng perpetual tối đa 16 móc kép/ô); hướng chạy phải cùng hướng với đường giá của câu (giá đang lên thì chạy lên là chính — chạy ngược hướng chỉ ở dạng chạy xuống kết câu).
- Mật độ toàn cục: tối đa 1 đoạn chạy mỗi câu và số ô chứa chạy dây không quá ~15% số ô của section (ngân sách tính bằng **số ô**, tách bạch với ngân sách móc đơn của chuông ở mục 4.3.1); section nào cũng phải có ít nhất một câu "sạch" không chạy để tai còn mốc so sánh.
- Velocity chạy theo vòng cung: nhẹ ở đầu đoạn, mạnh dần về nốt đích (khớp hairpin của câu), nốt đích nhận accent/tenuto của nốt dữ liệu như thường.

#### 4.3.4. Ràng buộc kỹ thuật chung của Barrios

- Tempo > 100 BPM: tremolo giảm mật độ theo lưới chốt sẵn, đếm **bên trong phách của meter**, không cắt ô thành các khúc 4 móc kép. Phách 4/4 và 3/4 dài 4 móc kép; phách 6/8 là phách chấm dôi, dài 6 móc kép (đúng ô dài 12 móc kép, hai phách mở ở móc kép 0 và 6). Trong mỗi phách đó chỉ còn **hai lần đánh**: móc kép 0 của phách là ngón cái (Trầm, hoặc Trung thế chỗ khi đổi hợp âm như thường lệ), móc kép 2 của phách là một nốt giai điệu ngân hết phần còn lại của phách. Các móc kép khác của phách không có nốt đánh mới. Ba chương guitar vượt 100 BPM, lấy từ bản đồ mục 4.0 và `span.py`: scherzo `1M` (120, **6/8**) và tháng khép `1Y` (108, **6/8**) dùng phách chấm dôi — ngón cái ở móc kép 0 và 6 của ô, giai điệu ở móc kép 2 và 8; chương III của `3M` (108, **4/4**) dùng phách đen — ngón cái và giai điệu ở móc kép 0 và 2 của từng phách đen. Cắt ô 6/8 thành khúc 4 móc kép đặt ngón cái ở móc 4, giữa nhóm đầu, và mở phách lớn thứ hai bằng nốt giai điệu. Đoạn chạy ở các chương này rút xuống tối đa 4 móc kép và chỉ còn dạng chạy lên đỉnh; perpetual bị tắt hẳn (ngón không kịp ở tempo đó trên đàn thật, và nghe sẽ thành tiếng rè).
- Nốt giai điệu tremolo và nốt chuông Preludio phải gán được trên dây 1/2 theo mô hình dây (mục 5.2) — việc này do sàn bè Cao bảo đảm sẵn: bước nén ở mục 3.2/3.3 đã giữ giai điệu ở hoặc trên `guitar_treble_floor` (59 trong không gian vang) trước khi renderer chạy, nên **không có chuyện renderer tự nâng từng ô lên một quãng tám** (việc đó sẽ phá tính liên tục của câu và mâu thuẫn mục 5.5). Nếu một nốt nén vẫn rơi dưới sàn (lỗi của bước nén, không phải của renderer), ô đó bỏ tremolo và viết nốt đơn thay thế, đồng thời test ở mục 8 phải bắt được trường hợp này. Đoạn chạy kiểm tra gán dây theo luật **tuần tự** của mục 5.2 (mỗi thế trong đoạn có khoảng phím ≤ 5, được đổi thế tại biên nhóm 4 móc kép) — không áp luật khoảng phím của hợp âm cho cả đoạn chạy, và không rút ngắn đoạn chạy vì tổng khoảng phím của nó vượt 5.
- Velocity tremolo của lưới đầy (`p–a–m–i`, tempo ≤ 100): lần lặp giai điệu đầu tiên của phách (móc kép 1, ngay sau ngón cái) = velocity giai điệu hiện tại, hai lần lặp sau thấp hơn 6–10 đơn vị và hơi lượn (ví dụ +0/−8/−4), tránh tiếng súng máy đều tăm tắp. Nốt Trầm ở móc kép 0 nhẹ hơn lần lặp đầu 4–8 đơn vị để giai điệu vẫn là nhân vật chính. Lưới giảm (mục trên) chỉ có một nốt giai điệu, ở móc kép 2 của phách: nốt đó lấy velocity giai điệu hiện tại, không còn đường +0/−8/−4; ngón cái vẫn nhẹ hơn nốt giai điệu 4–8 đơn vị.

---

## 5. Ràng buộc chơi được trên guitar thật

Guitar không phải piano thu nhỏ: một nốt có thể nằm trên nhiều dây, và hai nốt cùng vang không được trùng dây. Module guitar phải tự kiểm tra các ràng buộc sau, và có test khóa chúng (mục 8).

### 5.1. Âm vực và thứ tự bè
Như bảng 3.1: mọi nốt phát âm trong 40–83, Trầm 40–53, Trung 50–65, Cao 59–81 (vùng trên 81 tới 83 chỉ dành cho nốt chuông Preludio, không cho đỉnh đường giá), tại mỗi thời điểm tối đa 3 nốt vang thuộc 3 bè khác nhau, và khi cả ba cùng vang thì Trầm < Trung < Cao nghiêm ngặt. Một ngoại lệ duy nhất cho trần Trung 65: cú đánh **hợp âm khối** được cho bè Trung lên trên 65 theo luật thế ở mục 5.2 — giữ trần 65 tuyệt đối ở mọi cú khối sẽ làm fanfare của Grand Solo và chord-melody của Étude 11 mất bè Trung đúng ở đỉnh câu, nơi chúng cần đủ 3 nốt nhất.

### 5.2. Mô hình dây và phím — tính trên cao độ vang, hai luật khác nhau

Dây buông (cao độ vang): dây 6 = 40 (E2), 5 = 45 (A2), 4 = 50 (D3), 3 = 55 (G3), 2 = 59 (B3), 1 = 64 (E4). Mọi phép tính phím đều dùng **cao độ vang** `midi + key.semitones` (mục 3.1); cao độ viết trên khuông (đã cộng 12 vì transpose) không bao giờ được đưa vào đây. Một nốt vang `p` nằm trên dây `s` ở phím `p − open[s]`.

Giới hạn phím theo dây (đàn cổ điển tiếp cận phím cao ở dây trầm kém hơn dây cao vì khớp thân đàn quanh phím 12–14): dây 6–4 chỉ nhận phím 0–12, dây 3 nhận 0–17, dây 2–1 nhận 0–19. Bộ gán **ưu tiên thế thấp** (tổng phím nhỏ nhất) trước khi chấp nhận bất kỳ phép gán hợp lệ nào — một nốt chỉ được tính là chơi được khi tồn tại phép gán trong các giới hạn này, không phải cứ ≤ 19 trên mọi dây.

Hai luật khoảng phím, không trộn:

- **Nốt cùng vang (hợp âm/arpeggio đang ngân chồng)**: Chọn cho mỗi cụm tối đa 3 nốt một phép gán phân biệt (không trùng dây) sao cho khoảng phím (max − min trên các nốt bấm, bỏ dây buông) ≤ 5. Đây là luật duy nhất mà con số 5 áp dụng. Hai hệ quả của thực hành guitar cổ điển phải tôn trọng: (a) nốt **dây buông** không tính vào khoảng phím và không bị thế tay giới hạn — hợp âm khối gồm dây buông ở xa vùng bấm vẫn là hợp âm chơi được bình thường, không phải trường hợp ngoại lệ; (b) ở **cú hợp âm khối tại vùng cao** (giai điệu vang từ 80 trở lên, tức khoảng phím 16 trên dây 1), bè Trung không bị khóa ở trần vang 65 (khoảng phím 10 trên dây 3 — cách giai điệu hơn 5 phím nên mọi phép gán đều vỡ luật và ống sửa sẽ bỏ Trung): phép gán cho cú khối được tìm Trung **trong cùng thế với giai điệu**, tức âm hợp âm trên dây 2/3/4 có phím cách phím giai điệu ≤ 5 và cao độ vang thấp hơn giai điệu (thường là âm 3/7 ngay dưới giai điệu). Đây là cách người chơi thật đặt hợp âm ở thế XII–XVI; trần 65 chỉ áp cho bè Trung đi riêng lẻ, không áp cho Trung trong cú khối. Tiêu chí nghiệm thu của phép gán này là **khoảng phím**, không phải một cửa sổ cao độ: giai điệu vang 80 ở phím 16 dây 1 mà đặt Trung ở phím 9 dây 2 (vang 68) là cách 7 phím — vỡ luật dù 68 nằm trong bất kỳ khoảng "thường gặp" nào. Test và `assert_playable` chỉ đo khoảng phím và thứ tự cao/thấp, không khóa cao độ tuyệt đối của nốt Trung trong cú khối.
- **Nốt tuần tự (đoạn chạy dây, scale run)**: Không áp khoảng phím cho cả đoạn. Đoạn chạy được chia tại biên mỗi nhóm 4 móc kép thành các *thế*; mỗi thế phải tự có khoảng phím ≤ 5 và gán dây liên tục, giữa hai thế được **đổi thế** tự do (đó là cách Allegro Solemne chạy dài hơn 5 phím). `assert_playable` kiểm tra từng thế, không kiểm tra tổng khoảng của đoạn.

Khi một cụm cùng vang không gán được, renderer không sửa tại chỗ trong bộ kiểm tra — nó đi qua ống sửa nốt ở mục 5.5. Bộ kiểm tra ở đây (`assert_playable(score, key, profiles)`) là hàm thuần, chỉ báo lỗi, không sửa nốt.

### 5.3. Thứ tự tỉa bè khi quá tải
Với hợp âm ba, bảy, chín và add9: (1) bass gốc → (2) giai điệu → (3) âm 3 của hợp âm (bè Trung) → (4) âm 7/9 màu (bè Trung) → (5) âm 5. Bỏ từ dưới lên: âm 5 bỏ trước, rồi âm 9/7, không bao giờ bỏ âm 3 trước âm 5. Add9 của dialect `villa` đi đúng thứ tự này: bỏ quãng 5, còn 1–3–9.

Với `quality_group == "suspended"` không có âm ba để giữ. Quãng 2 hoặc quãng 4 chiếm chỗ (3); b7 chiếm chỗ (4); quãng 5 vẫn là (5) và bị bỏ trước. Sus2 và sus4 đã đúng ba nốt. 7sus4 bỏ quãng 5, còn 1–4–b7. Coi quãng 4 là màu được bỏ sẽ để lại mỗi gốc — mất đúng chất sus.

Khi giai điệu trùng âm bè Trung, bè Trung đổi sang âm hợp âm thấp hơn tiếp theo: còn trong dải Trung ở ngữ cảnh thường, nhưng ở **cú hợp âm khối** thì nốt thay phải là âm hợp âm cùng thế với giai điệu theo mục 5.2, kể cả khi nó vượt trần Trung — không bao giờ vượt lên trên hoặc trùng giai điệu.

### 5.4. Chuyển động bè — theo profile của từng lớp, không có luật chung

Không tồn tại một luật bass/trung áp cho cả ba phong cách. `assert_playable` và renderer đều nhận một **profile theo lớp chất liệu đang chạy**, và chỉ kiểm tra luật của profile đó:

| Profile | Luật bè Trầm trong ô | Luật bè Trung |
|---|---|---|
| `study` (Sor) | Chỉ gốc → quãng 5 → gốc gập quãng (mọi nốt đã gập vào dải Trầm); nhảy pitch-class khác chỉ ở biên ô | Chọn âm hợp âm gần nốt Trung trước nhất (liền bậc ưu tiên) |
| `grand` (Sor) | Như `study`, cộng hợp âm khối ở đầu câu và nốt dẫn gốc ô sau ở móc cuối câu | Như `study`, dày hơn theo mức biến tấu; trong cú khối được dùng phép gán cùng-thế trên trần Trung (mục 5.2) |
| `elegiaque` (Sor) | **Đi xuống liền bậc** theo thang ở cuối câu (mục 4.1); mẫu chấm dôi theo meter; gốc–quãng 5 chỉ ở ô mở câu | Thưa, liền bậc; appoggiatura chỉ ở bè Cao |
| `villa_pattern` | Gốc/quãng 5 theo vòng arpeggio; **nốt dẫn bán cung** về gốc ô sau ở móc cuối ô được phép và được chờ đợi | Theo vòng mẫu cố định, được nhảy theo sequence |
| `villa_chord` (No. 11) | **Nhảy rộng tự do** (gốc, âm 3 hoặc âm màu sus, quãng 5 ở bất kỳ thứ tự nào) trong dải Trầm — bước tay trái rộng là chất của lớp này | Âm màu ngồi ngay dưới giai điệu: âm 3/7 với hợp âm ba/bảy, quãng 2/4 hoặc b7 khi `suspended` (mục 5.3); ở vùng cao dùng phép gán cùng-thế trên trần Trung (mục 5.2) |
| `barrios_tremolo` | Ngón cái: gốc ở phách 1, quãng 5 ở phách 3 (4/4). Phách thường: không nốt Trung đánh mới, Trung chỉ ngân tiếp. Ngoại lệ duy nhất: phách đầu ô đổi hợp âm thì móc kép 0 là một nốt Trung mới và phách đó không có nốt Trầm riêng | Chỉ nốt ngân, hoặc nốt mới ở móc kép 0 thế chỗ Trầm khi đổi hợp âm (mục 4.3.2) |
| `barrios_preludio` / `barrios_chorale` | Gốc thưa đầu ô/đầu 2 ô; hợp âm thánh ca đánh cùng giai điệu ở phách mạnh | Âm hợp âm ngân dài, liền bậc |
| `barrios_run` | Gốc ở phách 1 và 3, nghỉ còn lại | Nghỉ; bè Cao chạy một mình (mục 4.3.3) |

Điểm chung duy nhất của mọi profile: âm vực và gán dây/phím (mục 5.1–5.2) và trần 3 nốt cùng vang. Ngoài điểm chung đó, test chơi được phải truyền đúng profile của từng đoạn; một test áp luật `study` lên đoạn Élégiaque/Villa là test sai, không phải nốt sai.

### 5.5. Ống sửa nốt của renderer (chính sách duy nhất, chạy từ Bước 1)

Renderer sửa nốt **khi dựng bè**, theo thứ tự cố định này cho mỗi cụm nốt cùng vang; `assert_playable` ở Bước 2 chỉ kiểm chứng kết quả, không sửa gì thêm:

1. Tính các cao độ ứng viên theo thứ tự ưu tiên ở mục 5.3 (Trầm gốc → Cao giai điệu → Trung âm 3 hoặc âm màu sus → Trung âm 7/9/b7 → Trung âm 5). Mọi ứng viên là **số viết trong không gian Đô**; không bước nào trong ống này cộng `key.semitones` vào nốt — cao độ vang chỉ được suy ra bên trong phép gán dây/phím ở bước 4 và trong test.
2. **Gập bass vào dải Trầm trong không gian viết**: nốt Trầm (gốc, quãng 5, hay "quãng 8") cộng/trừ 12 cho đến khi nằm trong [`guitar_floor`, `guitar_bass_top`] = [40 − semitones, 53 − semitones] theo số viết. Không bao giờ viết `gốc + 12` nguyên trạng khi nó vượt trần này. Ví dụ khóa lỗi lẫn không gian: với FPT (`+2`), khoảng viết hợp lệ là 38–51; một ứng viên viết 55 (vang 57) phải gập xuống 43 (vang 45) — test ở Đô không bắt được lỗi này vì ở Đô hai khoảng trùng nhau.
3. Tỉa xuống tối đa 3 nốt theo thứ tự ngược của mục 5.3 (bỏ âm 5 trước, rồi 7/9/b7, giữ âm 3 — hoặc quãng 2/4 khi hợp âm `suspended` — đến cuối).
4. Thử gán dây/phím theo mục 5.2 (bước này, và chỉ bước này, quy mỗi nốt viết ra cao độ vang `midi + semitones` để tính phím). Nếu hỏng: nâng bè Trung lên 12 (nếu vẫn trong [`guitar_mid_low`, `guitar_mid_high`] theo số viết và vẫn dưới bè Cao) rồi thử lại. Nếu cụm là **cú hợp âm khối** mà vẫn hỏng, thử tiếp phép gán cùng-thế của mục 5.2: đổi bè Trung sang âm hợp âm nằm ngay dưới giai điệu với phím cách phím giai điệu ≤ 5, kể cả khi nó vượt `guitar_mid_high` — bước này đứng trước mọi bước bỏ nốt, vì bỏ Trung ở cú khối đỉnh câu là hỏng đúng hai lớp chất liệu cần 3 nốt nhất.
5. Vẫn hỏng: đổi bè Trung sang âm hợp âm gần nhất còn lại. Hợp âm có âm ba thì đổi âm 3 ↔ âm 7. Hợp âm `suspended` không có âm ba: đổi giữa các âm màu còn lại (quãng 2 hoặc quãng 4 ↔ b7). Sus2 và sus4 chỉ còn một âm màu sau khi đã bỏ quãng 5, nên bỏ qua bước đổi này và rơi xuống bước 6. Đổi trong dải viết của bè Trung, hoặc trong vùng cùng-thế nếu là cú khối.
6. Vẫn hỏng: bỏ bè Trung, thử lại với Trầm + Cao. Cặp này gần như luôn gán được; nếu vẫn hỏng, gập Trầm thêm một quãng tám trong dải và thử lần cuối. Trường hợp cuối cùng này phải bằng 0 trong benchmark (mục 8) — nó tồn tại để renderer không bao giờ xuất nốt không chơi được, không phải để dùng thường xuyên.
7. Giai điệu (bè Cao) không bao giờ bị sửa bởi ống này ngoài bước nén ở mục 3.2; bass chỉ bị gập quãng tám, không đổi pitch-class.

Vì Grand Solo đã đánh hợp âm khối 3 nốt ngay ở Bước 1, ống này (ít nhất các bước 1–3 và 6 rút gọn) thuộc **Bước 1**, không đợi Bước 2. Bước 2 chỉ thêm bộ gán dây đầy đủ (bước 4–5) và `assert_playable` độc lập.

---

## 6. Biểu diễn trong code: một part, ba voice

### 6.1. `Score` và MusicXML
`Score` hiện có 5 trường part (`high`, `lead`, `support`, `comp`, `low`). Với guitar, quy ước:
- `lead` = bè Cao, `support` = bè Trung, `low` = bè Trầm; `high` và `comp` là tuple rỗng.
- `NoteEvent.voice` mang số voice trên cùng một khuông: Cao = voice 1, Trung = voice 2, Trầm = voice 3 (hiện mọi renderer đang để voice 1, riêng tay trái piano dùng voice 5/staff 2 — guitar không dùng staff 2).

`musicxml.py` cần nhánh riêng cho `variant == "guitar"`, và đường đi của part phải viết đúng theo code hiện tại (đây là chỗ dễ sai nhất):

- `parts_for(variant, ensemble)` trả `None` khi ensemble là `classic`, nên hàng `classic` **không** nằm trong `_ROWS` của `ensemble.py` — nó phải nằm ở `_PARTS_BY_VARIANT["guitar"]` trong `musicxml.py`, cạnh các hàng mặc định của bốn variant cũ. Chỉ `villa` và `barrios` mới có hàng trong `_ROWS`, và cả hai hàng đều là cùng một part duy nhất dưới đây.
- Part duy nhất là `("P1", "Acoustic Nylon", "Acoustic Guitar", "1", "25")`. **`<part-name>` bắt buộc là `Acoustic Nylon`**: tầng gắn sample khóa theo tên giọng qua `_VOICE_BY_SOUND`/`_xml_part_sounds` (đọc part-name/instrument-name), và tên giọng trong thư viện là `Acoustic Nylon`. Viết "Classical Guitar" vào part-name là không khớp sample nào và MuseScore sẽ rơi về MS Basic. `Acoustic Guitar` chỉ là `<instrument-name>` (tên nhạc cụ MusicXML), không phải khóa khớp giọng.
- Một khuông khóa Sol với `<transpose><octave-change>-1</octave-change>`, và `_guitar_part` phải truyền **cả cặp** như part bass hiện tại đang làm (`_bass_part`: `written_shift = 12 * BASS_WRITTEN_OCTAVES` cùng `octave_change = -BASS_WRITTEN_OCTAVES`): `_add_note(..., written_shift=+12)` để nốt trong XML viết cao hơn số score một quãng tám, và `octave-change = -1` để MuseScore hạ xuống đúng cao độ score cộng giọng nhà. Chỉ xuất `octave-change` mà quên `written_shift` thì MuseScore hạ cả part xuống một quãng tám thật, trong khi mọi test đọc `NoteEvent` vẫn xanh — lỗi này chỉ bắt được bằng test đọc nốt trong XML (mục 8). Ký hiệu này không ảnh hưởng phép tính phím ở mục 5.2. Cả ba voice viết chồng trong một measure. Cần hàm `_guitar_part` riêng, và `score_to_musicxml` phải rẽ nhánh guitar **trước** toàn bộ đường năm part P5–P4 hiện tại, kể cả `_part_list`. Harmony symbol và dynamics/hairpin gắn trên part guitar duy nhất (hairpin của bè Cao, dynamics theo band như hiện tại).
- Thêm `"guitar"` vào `VARIANTS` và thêm nhánh `variant == "guitar"` trong `render.py::_compose` phải đi **trong cùng một commit**: nếu `VARIANTS` đã chứa guitar mà `_compose` chưa rẽ nhánh, hàm sẽ chạy thẳng xuống cuối và lặng lẽ viết một bản giao hưởng năm part dưới tên guitar. Test tích hợp ở mục 8 phải khóa điều này (render guitar không bao giờ ra `Score` năm part/MusicXML năm part).
- **Ba voice trong một measure phải nối bằng `<backup>`, không phải bằng `<chord>`**: `_guitar_part` xuất lần lượt toàn bộ voice 1 của ô, rồi `<backup>` với duration bằng đúng độ dài ô để quay về đầu ô, rồi voice 2, `<backup>` lần nữa, rồi voice 3 — cùng cơ chế `_piano_part` đang dùng giữa hai staff, nhưng ở đây cả ba lần quay đều nằm trong một staff. Nối ba voice nối tiếp mà không backup thì ô dài gấp ba. Nốt của hai voice khác nhau **không bao giờ** được gắn cờ `<chord/>` dù cùng thời điểm đánh: cờ đó chỉ dành cho hai nốt cùng voice, cùng onset; hợp âm khối 3 nốt của guitar là ba nốt ở ba voice cùng onset, mỗi nốt đứng độc lập sau các `<backup>`.
- **Slur phải đánh số theo voice**: `_add_note` hiện khóa cứng `number="1"` cho mọi slur, nên ba voice sẽ dính chung một đường slur. `_guitar_part` phải tham số hóa số slur theo voice (slur của bè Cao mang số 1, Trung số 2, Trầm số 3 — hoặc ánh xạ tương đương), không sửa hành vi mặc định của các part cũ.
- **`with_rests()` gọi riêng cho từng voice**: hàm này lấp một lưới thời gian duy nhất và `written()` luôn gán `voice=1`. Phải chạy nó (hoặc bộ lấp rest tương đương) **ba lần, mỗi lần trên sự kiện của một bè**, rồi gán lại số voice 1/2/3 cho Cao/Trung/Trầm trước khi gộp. Gọi một lần trên cả ba bè đã gộp sẽ nuốt khoảng nghỉ của hai bè và chồng thời lượng lên nhau.

Về hướng cuống nốt (stem): giai đoạn đầu để MuseScore tự quyết theo voice, kiểm chứng bằng bản nhạc xuất thử; nếu cuống rối, bổ sung trường `stem` tùy chọn vào `NoteEvent` và xuất `<stem>` trong `_add_note` (voice 1 up, voice 3 down, voice 2 tùy ngữ cảnh). Không làm trước khi thấy bản nhạc thật.

Về lưới thời gian: `written()`/`with_rests()` trong `phrasing.py` đang khóa theo lưới móc đơn (vị trí = `beat × 2`). Sor và Villa-Lobos sống được trên lưới này (`divisions = 2`). **Barrios cần móc kép** (`divisions = 4`): phải hoặc mở rộng hai hàm trên nhận bước lưới theo `score.divisions`, hoặc renderer tremolo tự dựng `NoteEvent` trực tiếp (như `minimalist.py` đang làm với nốt 0.25 phách) và tự lấp rest theo lưới 16. Chọn cách thứ hai trong giai đoạn đầu để không đụng vào đường đi của 4 variant cũ; khi nào cần tremolo ngân qua biên ô thì mới tổng quát hóa. Ở cả hai lưới, việc lấp rest vẫn theo quy tắc ở trên: mỗi voice một lần gọi riêng, không gọi một lần cho cả ba bè.

### 6.2. Khung mở/kết (`intro`/`outro`, `warmup`/`cooldown`) và groove
`apply_daily_frame`/`apply_span_frame` (`daily_frame.py`, `movement_frame.py`) đang viết cho 5 part — guitar bỏ qua hai tầng này trong giai đoạn đầu: renderer guitar tự viết các ô khung thành texture pedal chủ âm thưa (bass + giai điệu nốt dài) ngay trong module guitar, dùng chính `slots` đã có các section đó. **Tên khung khác nhau theo loại bản và renderer phải nhận cả hai cặp**: khung của `DAILY_ENSEMBLE_SPEC` ở bản ngày là `intro`/`outro`; `warmup`/`cooldown` chỉ xuất hiện sau `attach_frame` của bản dài `1M`–`1Y`. Renderer chỉ nhìn `warmup`/`cooldown` sẽ bỏ trống 2 ô đầu và 2 ô cuối của mọi bản ngày — lỗi này không lộ ở test bản dài, nên test phải khóa cả section kind của `1D`. Về groove: `build_groove` không bật `tresillo` cho variant mới (mục 4.0), nên renderer guitar tự cài luật nhấn 3+3+2 của mình; các cờ groove còn lại đọc qua `groove_at(bar)` được nhưng không bắt buộc ở giai đoạn 1.

### 6.3. Tiếng đàn (MuseSounds — đã kiểm chứng)
Đã kiểm kê ngày 2026-10-23: máy đã cài **Muse Guitars Vol. 1** (`Owned` trong Muse Hub), và truy vấn trực tiếp cơ sở dữ liệu `.instruments` của MuseSampler thấy giọng **`Acoustic Nylon`** (id `13010`, `state = 1` — đang bật) cùng các giọng anh em (`Acoustic Steel Picked/Plucked`, `Electric LP/SC`). Đây là giọng nylon sáu dây fingerstyle — đúng âm sắc cần, và rủi ro "không có tiếng nylon" ở bản kế hoạch đầu đã được gỡ.

Cách gắn vào code hiện tại:
- Thêm một mục vào `_MUSE_VOICES` trong `audio.py`: `_MuseVoice((), ("Acoustic Guitar", "Classical Guitar"), "Acoustic Nylon")`. Không cần bịa `instrument_ids`: cơ chế khớp hiện tại đi qua `_xml_part_sounds` (đọc `<part-name>`/`<instrument-name>` trong MusicXML) → `_VOICE_BY_SOUND["Acoustic Nylon"]`, giống các mục có `instrument_ids = ()` sẵn như `French Horns a6`. Tuple part (ở `_PARTS_BY_VARIANT["guitar"]` cho `classic`, ở `_ROWS` cho `villa`/`barrios`) là `("P1", "Acoustic Nylon", "Acoustic Guitar", "1", "25")` — phần tử thứ hai là `<part-name>`, chính là khóa khớp giọng MuseSounds; `25` là GM Acoustic Guitar (nylon).
- Cần hiệu chỉnh `_VOICE_VOLUME_DB["Acoustic Nylon"]` khi nghe thử (giọng gảy thường nhỏ hơn dây/kèn; tham chiếu giọng guitar thép đang để `8` dB) và kiểm chứng fingerstyle của giọng này chơi đa bè ba voice chồng nhau có rõ từng lớp không — đây là mục nghe bắt buộc ở Bước 0, vì sample fingerstyle được thu cho giai điệu + đệm kiểu phổ thông, chưa chắc tách lớp cổ điển tốt.
- Lưu ý đường đi của part-name: với ensemble `classic`, tuple part ở trên đến từ `_PARTS_BY_VARIANT["guitar"]` trong `musicxml.py`; với `villa`/`barrios` đến từ `_ROWS` của `ensemble.py` — cả hai nguồn đều phải cho ra đúng tuple `("P1", "Acoustic Nylon", "Acoustic Guitar", "1", "25")`, không được lệch nhau.
- Phương án dự phòng nếu giọng này nghe không đạt: MS Basic GM nylon (program 25) qua MuseScore General. Dây thép (`Acoustic Steel Plucked`) không phải phương án thay thế — sai hẳn âm sắc cổ điển.

---

## 7. Thứ tự triển khai

Mỗi bước xong đều nghe được và kiểm thử được, theo đúng thứ tự ưu tiên tần suất dùng (`1D` trước, bản dài sau) như các kế hoạch sonify trước.

**Bước 0 — Kiểm chứng tiếng đàn và bản mẫu nghe (chưa đụng code chính)**
- Giọng nylon đã kiểm kê xong (mục 6.3: `Acoustic Nylon`, Muse Guitars Vol. 1). Còn lại: xuất một score guitar 1-part viết tay nhỏ (ba voice chồng, có cả đoạn arpeggio, hợp âm khối 3 nốt, tremolo móc kép, một đoạn chạy dây 8 móc kép và một nốt có ký hiệu `<harmonic>` thử) qua MuseScore để khóa: program 25, transpose −8va, cách MuseScore xử lý voice/stem, mức `_VOICE_VOLUME_DB`, giọng fingerstyle này tách ba lớp bè có rõ không, và nốt harmonic có được sample đáp ứng không (quyết định cho motif chuông của lớp Preludio, mục 4.3.1).
- Viết script nghiên cứu cạnh `research/sonify/harmony_benchmark.py`: render tay 1 phiên thật (ví dụ một phiên biến động và một phiên đi ngang) theo phác thảo Sor để nghe kiểm chứng âm vực nén (mục 3.2) trước khi khóa hằng số.

**Bước 0b — Nghiên cứu tổng phổ và catalog chất liệu (chưa đụng code chính, làm song song với Bước 0)**
- Sor: đọc *Grand Solo* Op. 14 và *Fantaisie élégiaque* Op. 59 (IMSLP, hết bản quyền), trích catalog lớp Grand Solo và Élégiaque ở mục 4.1: vị trí fanfare/điểm dừng trong form, cách biến tấu dày lên qua các lần trình bày lại, mẫu bass hành khúc và bass đi xuống cuối câu. Đối chiếu lại với một study Op. 35 để ranh giới ba lớp không bị lẫn.
- Villa-Lobos: đọc Étude No. 1, 2, 7, 11, trích catalog ở mục 4.2 — riêng No. 11 phải ghi rõ: nhịp đánh hợp âm ở đoạn chậm, những lần giai điệu ngồi trên hợp âm khối, và nhịp dồn hợp âm ở đoạn nhanh, để hàm `villa_layer` và quy tắc chord-melody có số liệu thật thay vì cảm tính.
- Barrios: đọc *La Catedral* đủ ba phần (Preludio Saudade, Andante Religioso, Allegro Solemne) và đối chiếu *El Último Trémolo*, trích catalog ở mục 4.3: nhịp và khoảng cách nốt chuông ở Preludio, nhịp hợp âm thánh ca ở Andante, và ở Allegro Solemne — độ dài một đoạn chạy dây, cách gom nhóm móc kép, điểm đổi hướng, nốt đích ở phách mạnh. Catalog này quyết định trực tiếp các hằng số của lớp Chạy dây (độ dài đoạn, ngân sách theo section) trong Bước 4.
- Đầu ra là một bảng trong tài liệu nghiên cứu (hoặc mục phụ lục của chính file này), mỗi mục catalog gồm: nhịp điệu, bố trí ba bè, điều kiện dữ liệu kích hoạt. Bước 1/3/4 chỉ code những mục đã có trong catalog.

**Bước 1 — Skeleton variant `guitar` + phong cách Sor, chỉ `1D`**
- `model.py`: thêm `"guitar"` vào `Variant`/`VARIANTS`; thêm `"villa"`, `"barrios"` vào `Ensemble`/`ENSEMBLES` (`classic` đã có).
- `ensemble.py`: `_ALLOWED["guitar"] = {"classic", "villa", "barrios"}`; chỉ thêm hai hàng `_ROWS[("guitar", "villa")]` và `_ROWS[("guitar", "barrios")]`, mỗi hàng là một part duy nhất `("P1", "Acoustic Nylon", "Acoustic Guitar", "1", "25")` (hàng `classic` nằm ở `_PARTS_BY_VARIANT` của `musicxml.py` theo mục 6.1 — thêm vào `_ROWS` là code chết). `keys.py::register_for` bổ sung bảy trường biên viết guitar dịch hai chiều (mục 3.3).
- Module mới `backend/app/sonify/guitar.py`: `render_guitar_score(...)` nhận cùng chữ ký như `render_jazz_score`, viết ba bè theo mục 4.1, `divisions = 2`, BPM 88 cho `1D`.
- `render.py::_compose`: rẽ nhánh `variant == "guitar"`; nhánh daily-ensemble tính cả guitar (`variant in ("symphony", "jazz", "minimalist", "guitar")`); `_finish` bỏ qua `fit_ensemble` 5-part và frame 5-part cho guitar.
- `musicxml.py`: `_PARTS_BY_VARIANT["guitar"]` (hàng classic một part, part-name `Acoustic Nylon`), `_guitar_part` một part ba voice nối bằng `<backup>` theo từng voice với slur đánh số theo voice (mục 6.1), và rẽ nhánh trong `score_to_musicxml` trước đường năm part. Cả hai thay đổi này cùng commit với việc thêm `"guitar"` vào `VARIANTS` và nhánh trong `_compose` (mục 6.1).
- `audio.py`: thêm `_MuseVoice` cho `Acoustic Nylon` (mục 6.3) và hiệu chỉnh `_VOICE_VOLUME_DB`; tăng `RECAP_REVISION`.
- Ống sửa nốt rút gọn của mục 5.5 (gập bass vào dải, tỉa 3 nốt, bỏ Trung khi cần) thuộc bước này, vì Grand Solo đánh hợp âm khối ngay từ đầu.
- Lớp Study của Sor trước (pattern viết theo `active_meter()`, dù `1D` mới chỉ chạy 4/4 — không khóa cứng số móc 0–7 vào code); hai lớp Grand Solo/Élégiaque vào cùng bước này nhưng sau Study, theo đúng catalog của Bước 0b: hàm `sor_layer(...)` với thứ tự ưu tiên và ngưỡng "họ câu" ở mục 4.1, cơ chế biến tấu theo lần lặp, scale run lên đỉnh, bass hành khúc theo meter và bass đi xuống ở mode Thứ, appoggiatura thật. Nếu thời gian phải cắt, Élégiaque được giữ trước Grand Solo vì chương chậm xuất hiện ở mọi bản dài.

**Bước 2 — Ràng buộc chơi được đầy đủ**
- Hoàn thiện ống sửa nốt của mục 5.5 bằng bộ gán dây/phím đầy đủ — tức **bước 4–5 của chính mục 5.5** (nâng Trung một quãng tám, đổi âm hợp âm, phép gán cùng-thế cho cú khối), không mở một chính sách cao độ thứ hai: mọi nốt vẫn là số viết trong không gian Đô đọc từ `active_register()`, và `semitones` chỉ được cộng bên trong phép tính phím của bước 4. Viết bộ gán "trên cao độ vang" là ghi cao độ vang vào `NoteEvent.midi` — đúng lỗi mục 3.3 đã khóa.
- `assert_playable(score, key, profiles)` độc lập, thuần kiểm tra (không sửa nốt): âm vực/thứ tự bè, gán dây cho cụm cùng vang, luật thế cho đoạn tuần tự, và luật chuyển động theo đúng profile của từng đoạn (mục 5.4). Dùng cho test và benchmark trên cả năm giọng nhà.

**Bước 3 — Villa-Lobos (`villa`)**
- Dialect hòa âm trước khi viết bè. Vỏ `HarmonyDialect`, `COMMON` và `dialect_for` trong `harmony.py`; `plan_slots` / `plan_markov_chords` nhận dialect; `_compose` truyền `dialect_for(ensemble)`. `Chord.degrees` và `quality_group == "suspended"` trong `chords.py`; `transpose_chord` dùng `degrees` khi trường này có giá trị. `VillaDialect` theo đúng luật catalog, thứ tự cạnh, cổng, `shares_root` và khoản màu 0.70 ở mục 3.4. Sor và Barrios không có khóa trong `DIALECTS`. Không gọi `jazz_chord` trên slot villa.
- Lớp Pattern (arpeggio mẫu cố định + trượt chromatic + tỉa theo mục 5.3, gồm ngoại lệ sus) theo mục 4.2, BPM 100 cho `1D`; hàm `villa_layer(...)` với **thứ tự ưu tiên khi nhiều lớp cùng khớp ở đầu mục 4.2** và lớp Chord-melody kiểu Étude No. 11 (hợp âm khối 3 nốt ở phách mạnh cho chương chậm/band `p`) vào ngay trong bước này, không để sau, vì chương chậm là nơi arpeggio thuần dễ chán nhất. Lớp Bậc thang (No. 7) có thể để cuối bước nếu phải cắt. Đường giai điệu giá của lớp Pattern nằm ở bè Cao trên lưới móc riêng, arpeggio chạy bên dưới (đoạn «Đường giá nằm ở đâu» ở mục 4.2) — không viết pattern như thể arpeggio *là* giai điệu. Ensemble này chỉ khác hàm viết bè trong cùng `guitar.py`, cộng dialect hòa âm ở trên.

**Bước 4 — Barrios (`barrios`)**
- Hàm `barrios_layer(...)` và cả bốn lớp theo mục 4.3. Thứ tự *triển khai* là Tremolo (lớp chính) → Preludio → Chạy dây → Thánh ca, nhưng thứ tự *chọn lớp khi chạy* là thứ tự ưu tiên ở đầu mục 4.3 (Preludio thắng ở đầu bài/chương, Chạy dây chỉ thắng ở điều kiện breakout, chương chậm mặc định Tremolo/Thánh ca) — hai thứ tự này khác nhau và test phải khóa thứ tự chọn. Tremolo khóa kiểu tuần tự `p–a–m–i` (mục 4.3.2): ở phách thường, móc kép 0 chỉ có nốt Trầm và không có nốt đánh mới nào của bè Trung trong cả phách; riêng phách đầu ô khi hợp âm đổi, móc kép 0 là một nốt Trung mới thế chỗ nốt Trầm (phách đó không có Trầm riêng) — đúng ngoại lệ mà test 7 chừa ra, không được triển khai thành cấm tuyệt đối. Chạy dây chiếm riêng bè Cao, nốt đích trùng nốt dữ liệu, nốt đầu được phép là nốt thang thấp hơn vài bậc (mục 4.3.3), ngân sách ~15% số ô. `divisions = 4`, BPM 76 cho `1D`; tự giảm mật độ tremolo/chạy dây khi BPM chương dài > 100 theo mục 4.3.4 — phách của lưới giảm là phách của meter, nên scherzo 6/8 không bị cắt thành khúc 4 móc kép. Motif chuông dùng nốt cao ngân chồng; ký hiệu harmonic thật chỉ xuất nếu phép thử ở Bước 0 cho thấy sample đáp ứng. Dialect hòa âm và lớp tiết tấu choro không thuộc bước này — chúng là Pha 1 và Pha 2 của [`docs/sonify-barrios-harmony.md`](./sonify-barrios-harmony.md), làm sau khi bước này đã có `barrios_layer`.

**Bước 5 — Bản dài `1W–1Y` và bản đồ nhịp guitar**
- `span.py`: thêm nhánh guitar trong `month_specs`/`quarter_specs`/`year_specs` theo bản đồ meter ở mục 4.0 (giữ số ô/BPM của giao hưởng, hoán đổi 6/8 ↔ 3/4 ở chương chậm và scherzo/tháng khép), đặt **trước** nhánh mặc định trong cả ba hàm. Nhánh guitar phải giữ nguyên các lần bọc `_with_trio(...)` đúng như nhánh mặc định (chương scherzo và tháng khép mùa `1Y`) — chỉ đổi meter, không đổi cấu trúc section — vì luật Élégiaque ở mục 4.1 đọc cờ `trio` từ chính các section đó; mất cờ là mất cả kích hoạt trio mà không test meter nào bắt được. Không cần nhánh guitar ở `_span_keys`, `_modes` và `home_pedal`: cả ba đã rơi về hành vi giao hưởng cho variant lạ (`home_pedal = variant != "minimalist"`), và đó chính là hành vi guitar cần — giọng nhà và mode theo character như giao hưởng, không swing. Cả ba phong cách dùng chung bản đồ meter; điểm khác nhau giữa chúng nằm ở pattern trong từng meter. Khung mở/kết của span do renderer guitar tự viết (mục 6.2). Thêm hàng đồng hồ `"guitar": (970.0, 1530.0, 2840.1)` vào test đồng hồ hiện tại.
- Test pattern phải chạy đủ ba meter (4/4 của `1D`/chương nhanh, 3/4 chương chậm, 6/8 scherzo) trước khi bước này được coi là xong — `1D` một mình không đại diện cho Élégiaque.
- Tăng `SPAN_REVISION`.

**Bước 6 — API và UI**
- `schemas.py`: thêm `"guitar"` vào Literal variant của `RecapResponse`/`SpanResponse`, thêm `"villa"`, `"barrios"` vào Literal ensemble (hai chỗ).
- `src/api/client.ts`: `RecapVariant` thêm `'guitar'`; `RecapEnsemble` thêm `'villa' | 'barrios'`; `ENSEMBLE_ROWS.guitar = [Sor, Barrios, Lobos]` (`classic`, `barrios`, `villa`).
- `SessionRecap.tsx` và `SpanRecap.tsx`: thêm `{ id: 'guitar', label: 'Guitar' }` vào `VARIANTS`. Nhãn trần được dùng vì hàng minimalist đã đổi thành «Guitar thép» (mục 1). Đồng thời đổi nhãn `ENSEMBLE_ROWS.minimalist` của hàng `guitar` từ «Guitar» thành **«Guitar thép»** trong `src/api/client.ts` — chỉ đổi nhãn hiển thị, id `guitar` và giọng `Acoustic Steel Plucked` không đổi. Cache ba phong cách guitar cổ điển tách tự nhiên thành `guitar`, `guitar-villa`, `guitar-barrios` và không bao giờ đụng stem `minimalist-guitar`, nên hàng lịch sử cũ vẫn phát đúng tiếng thép.
- Cập nhật `docs/sonify-instrument-sets.md` (thêm mục Guitar) và `docs/sonify-explain.md` (thêm variant vào bảng nhịp/BPM).

---

## 8. Kiểm thử và nghiệm thu

**Test tự động mới** (`backend/tests/test_sonify_guitar.py`, cộng khóa dialect trong `test_harmony.py` và khóa ensemble trong `test_ensemble.py`/`test_sonify_plan.py`):
1. **Âm vực trên cao độ vang, cả năm giọng nhà**: mọi nốt guitar phát âm (`midi + key.semitones`) nằm trong 40–83; Trầm trong 40–53, Cao ≥ 59 trừ khi bè Cao nghỉ; tại mỗi thời điểm đánh tối đa 3 nốt, thuộc 3 bè khác nhau và Trầm < Trung < Cao nghiêm ngặt khi cùng vang. Chạy trên cả 5 giọng nhà (VNM–Đô, FPT–Rê, HPG–Mi♭, VCB–Si♭, GMD–La). Đồng thời khẳng định trên **số viết**: Trầm viết trong [`40 − semitones`, `53 − semitones`], Trung viết trong [`50 − semitones`, `65 − semitones`] (trừ Trung của cú hợp âm khối theo mục 5.2), Cao viết trong [`59 − semitones`, `81 − semitones`] — **ngoại lệ trần**: riêng nốt chuông Preludio (nốt renderer tự sinh, không nằm trên đường giá đã nén) được viết lên tới `guitar_ceiling` (`83 − semitones`) theo mục 3.1, và test phải khẳng định mọi nốt Cao vượt `81 − semitones` đều là nốt chuông — đỉnh câu/breakout trên đường giá vẫn nằm trong cửa sổ nén, không ngoại lệ (khóa 81 tuyệt đối cho cả chuông sẽ mâu thuẫn mục 3.1 và tự đóng câu hỏi mở về chuông 82–83 ở mục 9). Không được kiểm tra trên cao độ Đô chưa dịch, và `<octave-change>-1` không được tham gia phép tính nào ngoài xuất bản nhạc.
2. Mỗi voice lấp đầy lưới thời gian không hở không chồng (tương tự `_full` trong `test_ensemble.py`), ở cả `divisions = 2` (Sor/Villa) và `divisions = 4` (Barrios).
3. Đường giai điệu sau nén vẫn đơn điệu theo giá trong từng câu (không nốt nào đảo hướng so với `raw_pitches` trong cùng câu, ngoài lượng tử hóa phách mạnh và hai ngoại lệ có tên: appoggiatura của Élégiaque và nốt đầu đoạn chạy dây của Barrios, xem mục 4). Một câu giá nằm hoàn toàn dưới sàn bè Cao phải được dịch **+12** vào cửa sổ Cao (tập ứng viên dịch gồm cả +12, mục 3.2) — không nốt Cao nào của câu đó được rơi xuống dưới `guitar_treble_floor` theo số viết. Ca biên bề rộng: một câu trải 50–70 (rộng 20, hẹp hơn cửa sổ 22, không mức dịch nào đặt vừa) sau dịch + nén phải nằm trọn trong cửa sổ viết — test không được chỉ kiểm tra câu rộng hơn cửa sổ.
4. **Pattern theo meter, không chỉ 4/4**: mỗi pattern Sor/Villa/Barrios được test ở cả ba meter. Cụ thể: bass hành khúc Élégiaque cho ra mẫu chấm-dôi 3+1 móc ở 4/4, mẫu tang-điệu 3/4 (móc 0 dài 3, móc 3 dài 1 đi xuống liền bậc, móc 4 dài 2) ở 3/4, và mẫu hai nhóm 2+1 ở 6/8 — mẫu 6/8 này phải được test cả ở section *ngoài* `trio` của một chương 6/8 có character `selloff` (Élégiaque phủ cả chương, không chỉ trio); lớp Pattern của Villa chạy một vòng 6 móc ở 6/8 (nhấn móc 0 và 3) và vòng 6 móc có hemiola ở band `f` ở 3/4; tremolo 6/8 ở tempo ≤ 100 đi 1 cú ngón cái + 5 lần lặp giai điệu trên một phách chấm-dôi. Bản đồ meter: `month_specs` guitar cho chương II là 3/4 và chương III là 6/8 (hoán đổi so với giao hưởng); ở `1Y`, tháng giữa mùa là 3/4 và tháng khép mùa là 6/8; `1D` vẫn 4/4. Test đồng hồ cộng thêm hàng `"guitar": (970.0, 1530.0, 2840.1)` và trần `47:21` cho `1Y`.
5. **Pattern theo band và lớp chất liệu**: ô `p` có đúng 1 nốt Trầm; ô `f` lớp Pattern của Villa có đủ 8 móc arpeggio *bên dưới* một giai điệu Cao đánh trên lưới riêng (không nốt Trung nào cao hơn hoặc trùng nốt Cao đang vang). Chọn lớp: chương chậm → Sor là `elegiaque`, Villa là chord-melody; `selloff` ở chương nhanh → `elegiaque`; đoạn giữa scherzo (cờ `trio`) ở mode Thứ với character `volatile` hoặc `calm` → `elegiaque` (không phải `grand`/`study`); tháng khép mùa `1Y` cũng vậy — section mang cờ `trio` ở mode Thứ → `elegiaque`, ở mode Trưởng → luật character thường, và nhánh guitar trong các hàm specs phải giữ cờ `trio` trên đúng các section như nhánh giao hưởng (test đếm số section trio trước/sau khi đổi meter); `rally`/`volatile` ở chương nhanh → `grand` **từ câu thứ hai trở đi** (không phải từ ô thứ hai — một câu dài nhiều ô, câu đầu vẫn là `study`). Biến tấu Grand Solo: hai câu liên tiếp thỏa tiêu chí "cùng họ" (cùng pitch-class gốc hợp âm mở đầu, cùng dấu contour, đỉnh lệch ≤ 2 bậc, độ dài lệch ≤ 4 móc) có mức figuration không giảm, và nốt phách mạnh của hai câu trùng khớp khung hợp âm. Chord-melody: tại phách mạnh của ô thuộc lớp này, cả ba bè đánh cùng một thời điểm và nốt Cao là nốt cao nhất; ở 3/4, cú khối chuẩn chỉ ở móc 0, cú ở móc 4 chỉ xuất hiện ở ô đỉnh câu hoặc ô kết câu, và **không ô 3/4 nào — kể cả ô cao trào — có cú khối ở móc 2** (luật dồn cách nhau 2 móc chỉ áp trong 4/4); ở 6/8, cú khối chỉ ở móc 0 và 3, không ở móc 2/4 kể cả khi câu đang dồn.
6. **Ưu tiên lớp khi xung đột** (test riêng cho các ca biên; band của câu là band của ô apex theo chốt ở mục 4.0, và mọi ca dưới đây đặt apex ở ô mang band đó): Villa — chương chậm + `f` + `volatile` + breakout → Bậc thang đúng một câu rồi quay lại Chord-melody; chương nhanh + `volatile` + `f` nhưng `rise < MIN_RISE` → Pattern, không phải Bậc thang. Barrios — chương chậm + câu breakout nhưng band chưa tới `f` → vẫn Tremolo; ô khung mở luôn là Preludio kể cả khi câu thỏa điều kiện chạy dây — test bằng section kind `intro` của `1D`, không chỉ `warmup` của bản dài; sau 2 câu tremolo liên tiếp ở chương chậm thì câu thứ ba là Thánh ca.
7. **Tremolo tuần tự**: trong một phách tremolo, móc kép 0 chỉ có đúng một nốt đánh — nốt Trầm (hoặc nghỉ/ngân tiếp), móc kép 1–3 là cùng một cao độ giai điệu, và không có nốt đánh mới nào của bè Trung trong cả phách, **trừ ngoại lệ đổi hợp âm**: ở phách đầu ô mà hợp âm đổi, móc kép 0 được là một nốt Trung mới *thay cho* nốt Trầm (phách đó không có nốt Trầm riêng, và tổng số nốt đánh ở móc kép 0 vẫn là một). 2 phách cuối câu đóng không còn tremolo, với "phách" tính theo đơn vị đen ở mục 4.3 (2 phách = 8 móc kép ở mọi meter). Appoggiatura: nốt phách mạnh của câu Élégiaque là nốt ngoài hợp âm kề trên/dưới nốt dữ liệu, và móc đơn kế tiếp giải quyết đúng vào nốt dữ liệu đó (tối đa 1 lần/câu). Ở chương có tempo > 100 BPM, lưới giảm đếm trong phách của meter (mục 4.3.4), không dùng chung một khúc 4 móc kép: scherzo `1M` (120, 6/8) và tháng khép `1Y` (108, 6/8) có ngón cái ở móc kép 0 và 6, giai điệu ở móc kép 2 và 8, và không có nốt đánh mới ở các móc còn lại của hai phách chấm dôi; chương III của `3M` (108, 4/4) có ngón cái ở móc kép 0 và giai điệu ở móc kép 2 của từng phách đen. Test 4 (1 ngón cái + 5 lần lặp trên phách chấm dôi) chỉ áp cho tremolo đầy, tempo ≤ 100 — scherzo không phải thỏa cả hai.
8. **Chạy dây**: nốt *đích* (cuối đoạn) trùng nốt dữ liệu tại phách mạnh đích; nốt đầu được phép là nốt thang thấp hơn đích 3–5 bậc và test không được đòi nó trùng nốt dữ liệu; mọi nốt ở phách mạnh trong đoạn giữ nguyên cao độ so với bản không-chạy; riêng dạng perpetual, móc kép 0 của mỗi phách trùng nốt giai điệu đang giữ còn móc kép 2 (mốc móc đơn giữa phách) là nốt chạy — test không được đòi nó là nốt dữ liệu; trong thời gian chạy, bè Cao không có nốt giữ song song nào khác và bè Trung nghỉ; đoạn chạy chia được thành các thế tay liên tiếp mỗi thế ≤ 5 phím (được phép đổi thế ở biên nhóm 4 móc kép), và tổng khoảng phím của cả đoạn **không** bị giới hạn 5; không section nào có quá ~15% số ô chứa chạy dây; ngân sách chuông Preludio tính bằng móc đơn (`bell_budget`) tách khỏi giới hạn số nốt (1 nốt/2 ô) — phiên có `rel_span ≤ 0.5%` cho ra đúng 0 nốt chuông.
9. **Chơi được và ống sửa nốt**: `assert_playable(score, key, profiles)` chạy trên cả năm giọng nhà — cụm cùng vang phải gán được dây với khoảng ≤ 5 phím và giới hạn phím theo dây (6–4 ≤ 12, dây 3 ≤ 17, dây 1–2 ≤ 19); chuyển động bass hợp lệ theo *profile của lớp đó* (test phải khẳng định bass đi xuống liền bậc của Élégiaque và nốt dẫn bán cung của Villa **đạt**, trong khi cùng chuyển động đó ở lớp Study thì bị báo lỗi — không có luật bass chung). Ống sửa nốt: test gập bass phải chạy ở giọng khác Đô — với FPT (`+2`), ứng viên bass viết 55 phải thành 43 (số viết trong [38, 51], vang trong [40, 53]), và một test chỉ chạy ở Đô bị coi là chưa khóa lỗi này. **Hợp âm khối ở đỉnh**: cụm khối có giai điệu vang ≥ 80 phải giữ đủ 3 nốt với bè Trung nằm ngay dưới giai điệu trong cùng thế (phím cách phím giai điệu ≤ 5, được vượt trần vang 65) — không được bỏ âm 3 ở những cú hợp âm có âm ba, và không được bỏ quãng 2/4 ở cú `suspended`; trường hợp "gập lần cuối" ở bước 6 của mục 5.5 xảy ra 0 lần trên bộ benchmark 5 mã × 4 tính cách, và số ô phải bỏ hẳn bè Trung (cũng ở bước 6, trước gập lần cuối) không vượt **1% tổng số ô** của benchmark — không ô nào trong số đó là ô cú hợp âm khối.
10. **Tích hợp part/nhãn**: render variant `guitar` ra MusicXML có đúng **một** `score-part` với `<part-name>Acoustic Nylon</part-name>`, một `<transpose>` với `octave-change = -1`, program 25, ba voice phân biệt — và không bao giờ ra bản 5 part kiểu giao hưởng (khóa việc thêm `VARIANTS` mà quên nhánh `_compose`). Phân tích XML: trong mỗi measure, tổng duration của từng voice bằng đúng độ dài ô, có hai `<backup>` nối ba voice (không có ô nào dài gấp ba), không nốt nào của voice khác mang cờ `<chord/>` chung với voice khác, và số slur của ba voice khác nhau; khóa cặp transpose bằng một nốt cụ thể — ở giọng Đô, một nốt score có `midi` viết 40 phải xuất thành pitch **E3** trong XML cùng `octave-change = -1` (thiếu `written_shift = +12` thì nốt này thành E2 và MuseScore phát thấp hơn một quãng tám, dù test âm vực trên `NoteEvent` vẫn xanh); `ensemble_for("guitar", "villa")` hợp lệ, `ensemble_for("guitar", "wood")` ném lỗi; nhãn variant là «Guitar», hàng minimalist `guitar` hiển thị «Guitar thép», ba hàng ensemble là Sor, Barrios, Lobos, và stem cache `minimalist-guitar` không đổi.
11. **Dialect hòa âm, chỉ villa**: cùng một dãy `raw_pitches`, `plan_slots` của symphony và của guitar `classic` / `barrios` không sinh kind `suspended-second`, `suspended-fourth` hay chữ `add9`. Guitar `villa`, gốc trước là C, phách mạnh là F và mọi phách mạnh khác thuộc {C, F}: ra `Csus4` khi `held_bars` của C là 1, khi `held_bars >= 2`, khi ô đó mở section, và khi đang giữ `Csus4` mà F còn ở phách mạnh — cả bốn ca này chạy ở `rally` lẫn ở character không trừ bias của F. Riêng ca đang giữ `Csus4` ở `rally`, mọi móc của ô, không chỉ phách mạnh, cũng thuộc {C, F}: bốn móc yếu của A nặng 0.08 (`WEAK_BEAT_WEIGHT` nhân từng móc) và làm F rẻ hơn. Cùng ô đó mà không có F ở phách mạnh (chỉ C hoặc G) thì không ra `Csus4`. Cùng ô đó mà thêm A ở phách mạnh thì ra F hoặc Fmaj7, không ra `Csus4`. Ô đầu, chưa có hợp âm trước, không phải pedal, uptrend hoặc downtrend, character không phải `selloff`, phách mạnh là F và mọi phách mạnh khác thuộc {C, F}: ra F hoặc Fmaj7, không ra `Csus4`, và F không bị hút về E. Cùng ô đầu đó ở `selloff` mà phách mạnh chỉ là F thì ra Dm, không ra F. Cùng ô đầu ở sideway không được đòi F. Ô có cả E lẫn D ở phách mạnh, gốc trước là C: ra `Cadd9` khi `held_bars` là 1, khi `held_bars >= 2`, và khi ô mở section; `Asus4`, `A7sus4` và `Dsus2` không được thắng các ca đó. Ô chỉ có E ở phách mạnh, `held_bars == 1`, ra C hoặc Cmaj7, không ra `Cadd9`. `same_harmonic_root(C, Csus4)` là sai; planner vẫn coi đó là cùng gốc qua `shares_root`. Add9 thứ chỉ có `Cm add9` và `Fm add9`, không có `Ebadd9` hay `Abadd9`. Ở thứ, `Ebsus2` → `Eb` được phép. Ô pedal vẫn là C / Cmaj7 khi nốt thô là F. `transpose_chord` của `Csus4` sang một giọng có dấu viết quãng 4 là quãng 4, không thành âm ba tăng. `fifth_above_bass` của mọi hợp âm villa đọc đúng quãng 5 ở `pitches[2]`. Hợp âm villa không giao thang của mode bị loại lúc dựng `extra()`, trước khi quantize chạy. Danh sách 7sus4 trưởng gồm `E7sus4` và không gồm `B7sus4`; danh sách thứ lấy gốc `MINOR_DIATONIC` (có A♭, E♭) và có `C7sus4`, `D7sus4`, `F7sus4`, `G7sus4`, không có `A7sus4`. Cú hợp âm khối sus giữ quãng 2 hoặc quãng 4; quãng 5 của 7sus4 được bỏ trước hai âm đó; bước 5 của ống sửa không đi tìm âm 3 của hợp âm sus. `dialect_for("classic")` và `dialect_for("barrios")` là `COMMON`, và `COMMON.allowed` trả `True`.

**Nghe đối chứng** (theo checklist sẵn có của dự án): 5 mã × 4 tính cách thị trường (`rally`, `selloff`, `volatile`, `calm`) ở `1D` và `1M`, nghe riêng từng phong cách:
- [ ] Sor: câu nhạc có nghe ra câu hỏi–đáp và điểm kết câu không? Bass có lấn giai điệu không? Lớp Grand Solo — lần trình bày lại của cùng một ý có nghe ra là biến tấu dày lên chứ không phải lặp lại y hệt không? Lớp Élégiaque ở chương chậm/phiên bán tháo — bass hành khúc và đoạn bass đi xuống có tạo được màu tang buồn khác hẳn lớp Study không, hay vẫn nghe như study chậm?
- [ ] Villa: mẫu arpeggio lặp có tạo đà cuộn mà không che đường giá (nốt Cao vẫn là nốt nổi nhất) không? Lớp Chord-melody (No. 11) ở chương chậm — hợp âm khối 3 nốt có hát như giai điệu trên hợp âm không, có bị nặng/đục ở vùng Trung không? Ô nào gốc đang được giữ và giá chỉ ngồi trên quãng 2 hoặc quãng 4 của gốc đó có nghe sus không, kể cả khi character là `rally`? Ô đầu không phải pedal, uptrend hoặc downtrend, không phải `selloff`, ngồi trên F có về hợp âm F, chứ không bị kéo về E và cũng không thành sus? Ô `selloff` chỉ ngồi trên F có về Dm không? Ô có cả âm ba lẫn quãng 9, gốc đã giữ từ hai ô, có nghe add9 chứ không nghe sus của gốc A hoặc D không?
- [ ] Barrios: đoạn mở Preludio — nốt chuông cao có gợi được không gian "nhà thờ" và nhường rõ cho câu đầu tiên không, hay nghe như nốt điểm cao lạc chỗ? Tremolo có ngân mượt, không thành tiếng rè đều? Đoạn chạy dây lên nốt breakout có nghe như một hơi thở dồn tới đỉnh không, và sau khi chạy xong có còn nhận ra đường giá ở các phách mạnh không (hay chạy dây đã thành nhân vật chính)? Đoạn tắt tremolo cuối câu có nghe như lấy hơi không?
- [ ] Cả ba: phiên đi ngang (`calm`, biên độ < 0.5%) có bị trang trí quá tay không (ngân sách điểm cao/breakout vẫn theo `bell_budget` hiện tại)?
- [ ] Nhịp điệu: ở bản `1M`, chương chậm 3/4 có nghe ra nhịp ba chậm (khác hẳn 6/8 của chương scherzo phía sau) không, hay mọi chương vẫn nghe như 4/4 đổi tốc độ? Lớp Pattern của Villa ở 3/4 band `f` có nghe ra hemiola không? Élégiaque ở 3/4 có nghe ra nhịp tang trong điệu van chậm không?
- [ ] Tremolo Barrios nghe có thành một đường giai điệu ngân liền (bass tách riêng ở đầu phách) không, hay nghe như bốn nốt chồng nhau rè đều? Đoạn chạy dây có nghe ra điểm rơi ở phách mạnh đích không, và nốt đầu thấp hơn có nghe như lấy đà tự nhiên không?

**Kiểm chứng chơi được**: in MusicXML của 2–3 bản mẫu, đưa một người chơi guitar cổ điển đọc thử (hoặc tự kiểm tra bằng mô hình dây ở bước 2) — tiêu chí: không ô nào bị báo không gán được dây sau khi tỉa bè ở mức phải bỏ âm 3.

---

## 9. Rủi ro và câu hỏi mở

| Rủi ro | Mức | Cách xử lý trong kế hoạch |
|---|---|---|
| MuseSounds không có giọng nylon | ~~Cao~~ Đã gỡ | Đã kiểm kê 2026-10-23: `Acoustic Nylon` (Muse Guitars Vol. 1, id 13010, đang bật). Rủi ro còn lại chỉ là chất lượng tách bè của sample fingerstyle — nghe kiểm chứng ở Bước 0, dự phòng MS Basic GM nylon |
| Nén đường giá 4 quãng tám xuống ~2 quãng tám làm mất chi tiết phiên biến động mạnh | Trung | Dịch quãng tám theo câu kiểu jazz trước, chỉ nén khi bất khả kháng (mục 3.2); nghe đối chứng ở bước 0 |
| Tremolo suốt bản dài gây mệt tai | Trung | Quy tắc bật/tắt theo band và cuối câu (mục 4.3); giảm mật độ khi BPM cao |
| Đoạn chạy dây lấn át dữ liệu, nghe như phô diễn | Trung | Ràng buộc trung thực ở mục 4.3.3: nốt đích trùng nốt dữ liệu ở phách mạnh (nốt đầu được phép thấp hơn vài bậc để lấy đà), phách mạnh trong đoạn giữ nguyên cao độ, ngân sách ~15% số ô/section, mỗi section giữ ít nhất một câu "sạch"; test tự động khóa các điều này |
| Bản đồ nhịp guitar lệch đồng hồ bản dài | Trung | Guitar dùng cùng số ô và BPM như giao hưởng, chỉ hoán đổi 6/8 ↔ 3/4 (cùng 6 móc/ô) nên tổng thời lượng không đổi; hàng đồng hồ `"guitar"` khóa trần `47:21` ở mục 8. Đổi nhịp *trong* một chương và rubato bị loại có chủ đích vì sẽ phá `piece_seconds`/playhead (mục 4.0) |
| Sample `Acoustic Nylon` không chơi harmonics | Thấp | Motif chuông của Preludio mặc định dùng nốt cao ngân chồng (campanella), không phụ thuộc harmonics; chỉ xuất `<harmonic>` nếu phép thử Bước 0 đạt |
| Hợp âm 9th/âm mượn không gán được dây | Trung | Tỉa bè theo thứ tự cố định (mục 5.3); test 9 khóa: ô phải bỏ hẳn bè Trung ≤ 1% tổng số ô benchmark (không ô nào là cú hợp âm khối), gập lần cuối bằng 0 |
| Sus bị trải lên ô chỉ có gốc, F của câu bị hút về E, hoặc add9 thua `Asus4` | Trung | Khoản 0.70 chỉ khi đã có hợp âm trước, cùng gốc, và phách mạnh là âm màu (mục 3.4). Ô đầu uptrend/downtrend về F; `selloff` về Dm; sideway không khóa về F. Test 11 khóa cả lần giữ sus ở `rally` lẫn `Cadd9` khi `held_bars >= 2`. `jazz_chord` không chạy trên slot villa |
| `_guitar_part` một part làm lệch các giả định 5-part ở nơi khác (frame, groove, player) | Trung | Bỏ qua frame 5-part cho guitar, renderer tự viết khung; rà `slice_score` trong `span.py` (đang truy cập đủ 5 trường — tuple rỗng vẫn an toàn) |
| Live stream chưa có guitar | Thấp | Ngoài phạm vi giai đoạn đầu; nếu làm sau, `voices.py` cần một "wave" gảy riêng và đó là việc tách biệt |

**Câu hỏi mở để chốt khi nghe bản mẫu bước 0** (không chặn việc bắt đầu): (1) Tempo `1D` ba phong cách ở bảng mục 4 có đúng cảm giác không; (2) nốt chuông Preludio có nên dùng tới vùng 82–83 (ngoài trần bè Cao thường 81) hay khóa ở 81; (3) Barrios ở chương chậm bản dài có nên là phong cách mặc định gợi ý cho người dùng chọn `barrios`, hay giữ nguyên tắc người dùng tự chọn hết.

---

## 10. Tóm tắt file chạm tới

| File | Thay đổi |
|---|---|
| `backend/app/sonify/guitar.py` | **Mới** — renderer ba phong cách, pattern theo meter/band/lớp, ống sửa nốt (mục 5.5), `assert_playable` theo profile |
| `backend/app/sonify/harmony.py` | **Mới** — `HarmonyDialect`, `COMMON`, `VillaDialect`, `dialect_for` (mục 3.4). Sor và Barrios không có khóa |
| `backend/app/sonify/chords.py` | `Chord.degrees`; `quality_group` `"suspended"`; hằng kind sus2/sus4/add9/7sus4 |
| `backend/app/sonify/form.py` | `plan_slots` / `plan_markov_chords` nhận dialect; nhánh cạnh dialect không nhân `prob * 2` |
| `backend/app/sonify/model.py` | Thêm variant `guitar`, ensemble `villa`/`barrios` |
| `backend/app/sonify/keys.py` | Bảy trường biên viết guitar trong `Register`/`register_for`, dịch hai chiều theo giọng nhà (mục 3.3). `transpose_chord` dùng `degrees` khi có |
| `backend/app/sonify/ensemble.py` | `_ALLOWED["guitar"]`; chỉ `_ROWS` cho `villa`/`barrios` (hàng `classic` ở `musicxml.py`), docstring về ensemble = phong cách |
| `backend/app/sonify/render.py` | Rẽ nhánh guitar trong `_compose` (cùng commit với `VARIANTS`), daily-ensemble gồm guitar, bỏ frame 5-part cho guitar, truyền `dialect_for(ensemble)` vào `plan_slots` |
| `backend/app/sonify/musicxml.py` | `_PARTS_BY_VARIANT["guitar"]` (part `Acoustic Nylon` cho `classic`), `_guitar_part` 1 part 3 voice, rẽ nhánh trước đường 5 part |
| `backend/app/sonify/audio.py` | Thêm `_MuseVoice` `Acoustic Nylon` + hiệu chỉnh volume, tăng revision |
| `backend/app/sonify/span.py` | Nhánh guitar trong `month_specs`/`quarter_specs`/`year_specs`: hoán đổi 6/8 ↔ 3/4 ở chương chậm/scherzo (mục 4.0), tăng `SPAN_REVISION` |
| `backend/app/schemas.py` | Literal variant/ensemble (2 chỗ) |
| `src/api/client.ts` | Type + `ENSEMBLE_ROWS.guitar`; đổi nhãn hàng `guitar` của minimalist thành «Guitar thép» |
| `src/components/SessionRecap.tsx`, `SpanRecap.tsx` | Thêm lựa chọn variant «Guitar» |
| `backend/tests/test_sonify_guitar.py` | **Mới** — các khóa ở mục 8 |
| `backend/tests/test_harmony.py` | Khóa dialect mục 8.11: villa sinh sus đúng ô, symphony/`classic`/`barrios` không sinh |
| `docs/sonify-instrument-sets.md`, `docs/sonify-explain.md` | Cập nhật sau khi nghe đạt |
