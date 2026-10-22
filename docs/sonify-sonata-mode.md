# Chủ âm của bản nhiều chương

Kế hoạch giọng cho giao hưởng, jazz và ambient từ 1M trở lên. Nhịp và khung chương nằm ở `docs/sonify-meter-frame.md`. 1D và 1W giữ một giọng như hiện tại. Tối giản giữ `month_keys` và `quarter_keys`. 1Y của mọi dạng vẫn đi theo mùa trên vòng giọng, vì mỗi tháng là một bài trong tổ khúc bốn mùa.

## Hiện trạng

Một chương được soạn trong không gian Đô trưởng. `KeySpec.semitones` dịch cao độ lúc ghi MusicXML, và `KeySpec.fifths` là hóa biểu. Vòng giọng là năm giọng trưởng, mỗi bước cách nhau hai hoặc ba semitone: Mi♭, Si♭, Đô, Rê, La. Mỗi mã có một giọng nhà trên vòng đó. FPT ở Rê, VNM ở Đô, HPG ở Mi♭, VCB ở Si♭, GMD ở La.

`month_keys` dựng sonata bốn chương: chương I và IV ở giọng nhà, chương II bước sang một giọng kế bên theo tính cách tuần, chương III lấy giọng kế bên còn lại. `quarter_keys` làm vậy với chương chậm của 3M. Bài kiểm tra `test_month_movements_one_two_and_three_use_three_keys` khóa ba tên giọng khác nhau trong ba chương đầu.

Với tuần đi ngang hoặc giảm, chương II đi xuống vòng. Với tuần tăng, chương II đi lên vòng.

| Giọng nhà | 1M, tuần II đi ngang hoặc giảm | 1M, tuần II tăng |
|---|---|---|
| Đô | Đô, Si♭, Rê, Đô | Đô, Rê, Si♭, Đô |
| Rê | Rê, Đô, La, Rê | Rê, La, Đô, Rê |
| La | La, Rê, Đô, La | La, Đô, Rê, La |
| Si♭ | Si♭, Mi♭, Đô, Si♭ | Si♭, Đô, Mi♭, Si♭ |
| Mi♭ | Mi♭, Si♭, Đô, Mi♭ | Mi♭, Đô, Si♭, Mi♭ |

3M chỉ đổi chương II, rồi chương III về giọng nhà. Một mã giọng Rê mà chương chậm tăng sẽ nghe Rê rồi La rồi Rê. Một mã giọng Đô mà chương II tăng sẽ nghe Đô rồi Rê rồi Si♭ rồi Đô.

Bên trong một chương còn một lần đổi chủ âm nữa. `tonic("downtrend")` là La thứ, và vòng sideway là Đô trưởng xen La thứ. Phách đầu câu được thưởng khi hợp âm là chủ âm của regime, nên một đoạn giảm lấy La làm gốc. Người nghe nghe gốc nhảy Đô sang La giữa chương, rồi sang giọng của chương sau.

Hai lớp này cộng lại thành những bước Đô, Rê, La. Đó là đổi bậc của chủ âm. Sonata cổ điển hầu như giữ một gốc cho cả tác phẩm. Màu đổi bằng cách chuyển từ trưởng sang thứ cùng tên, hoặc từ thứ sang trưởng cùng tên.

## Quy tắc

Giao hưởng 1M và giao hưởng 3M dùng một giọng nhà cho mọi chương. `semitones` không đổi giữa chương I và chương cuối, nên âm vực cũng không nhảy. Chương khác nhau ở mode.

| Tính cách chương | Mode |
|---|---|
| rally | trưởng |
| calm | trưởng |
| selloff | thứ cùng gốc |
| volatile | thứ khi regime đóng là downtrend, trưởng trong các trường hợp còn lại |

Một tháng bốn tuần đều tăng vẫn là bốn chương trưởng trên cùng một gốc. Tempo và mật độ hợp âm của chương chậm vẫn phân biệt chương II. Mode chỉ lật khi chính chương đó giảm, hoặc khi chương biến động kết bằng downtrend.

Hợp âm đi qua trong câu giữ chức năng của giọng. Chương trưởng: Rê thứ là bậc ii, Sol là bậc V, Fa là bậc IV. Chương thứ: bậc ii là Rê thứ bảy giảm năm (`Dm7♭5`, gồm La♭), bậc V vẫn là Sol hoặc Sol bảy, bậc IV là Fa thứ. Những hợp âm đó không phải chủ âm mới.

Chủ âm đạp của intro, của phách đầu mỗi câu, và của outro là hợp âm bậc I của mode chương đó.

- Chương trưởng: Đô và Đô trưởng bảy. La thứ vẫn được đi trong câu, với vai bậc vi. Intro, outro và phách đầu câu không thưởng cho La thứ.
- Chương thứ: Đô thứ và Đô thứ bảy. Đó là hạ bậc ba của chính hợp âm Đô, không phải chuyển sang La.

`finale_outro` giữ nguyên. Khi nó bật, chương cuối đã cùng mode với nốt kết: mở tăng và kết giảm thì cả chương cuối là thứ, mở giảm và kết tăng thì cả chương cuối là trưởng. Không thêm một lần lật mode riêng ở coda.

## Jazz: set bốn bài

Jazz 1M là một set: head, ballad, bài ngắn, finale. Mỗi chương là một bài, một giọng. Giọng đứng yên suốt bài. Finale về giọng nhà, nên set khép lại đúng chỗ đã mở.

| Chương | Vai | Gốc | Mode |
|---|---|---|---|
| I | head | giọng nhà | theo tính cách tuần, bảng ở trên |
| II | ballad | giọng nhà | theo tính cách tuần. Ballad nghe ra ở 12/8, swing tắt, và tempo chậm |
| III | bài ngắn | một bước trên vòng | theo tính cách của chính tuần đó |
| IV | finale | giọng nhà | theo tính cách tuần |

Chương III là bài duy nhất được đổi bậc. Bước lấy từ `_chapter_two`, với tính cách của chương III. Tuần tăng đi lên vòng. Tuần giảm hoặc đi ngang đi xuống vòng. Tuần biến động chọn phía nào chung nhiều âm hơn với chương trước. Giọng nhà Đô thì chương III là Rê khi tuần tăng, và Si♭ khi tuần giảm. Giọng nhà Rê thì chương III là La khi tuần tăng, và Đô khi tuần giảm. Mode của bài ngắn vẫn là trưởng hoặc thứ cùng tên của giọng vừa chọn.

Bên trong head, ballad và finale, chỉ đoạn giữa được rời gốc. Đó là câu tương phản 24 ô của chương I và chương IV, và 16 ô đoạn giữa của chương II. Đoạn này là bridge: phách đầu câu thưởng cho bậc IV của mode bài đó. Đô trưởng thì bridge về Fa. Đô thứ thì bridge về Fa thứ. Hai ô cuối bridge ưu tiên Sol hoặc Sol bảy, để câu trở lại rơi về bậc I. Các câu A, intro và outro giữ bậc I của bài. La thứ không làm chủ âm của câu.

Bài ngắn không có bridge sang giọng thứ tư. Cả chương III ở một giọng.

Jazz 3M là set ba bài: mở, ballad, khép. Cả ba giữ giọng nhà, mode theo từng tháng. Ballad vẫn có bridge sang bậc IV rồi về. Không có bài nào bước trên vòng, vì set ba bài không có ô bài ngắn.

## Ambient: một pedal

Ambient 1M và 3M giữ một gốc cho mọi chương, là giọng nhà. Mode từng chương theo bảng tính cách. Chương chậm là thứ cùng gốc khi tuần đó giảm. Tuần tăng thì ballad ambient vẫn trưởng: sự tĩnh nằm ở drone, kính thưa, và nhịp 6/4, không nằm ở việc đổi giọng.

Chương scherzo ambient đổi sang 3/4 trên cùng pedal. Đổi thêm giọng ở đây đánh thức tai đúng lúc nhịp đã là tương phản.

Bên trong chương, drone không cadence sang chủ âm khác. Đoạn giữa đổi màu hợp âm phía trên pedal, rồi gốc đứng yên. Intro, phách đầu câu và outro là bậc I của mode. La thứ không nhận thưởng chủ âm.

## Cách viết chương thứ

Score vẫn soạn ở không gian Đô, rồi dịch đúng `semitones` của giọng nhà. Chương thứ không chọn một `KeySpec` khác trên vòng.

Hóa biểu là thứ tự nhiên cùng tên của giọng nhà. Dịch cao độ giữ nguyên. Si tự nhiên trên ô Sol là dấu hóa bất thường, viết theo hợp âm Sol, không đưa vào hóa biểu.

| Giọng nhà | Hóa biểu trưởng | Hóa biểu thứ cùng tên |
|---|---|---|
| Đô | 0 | 3 giáng |
| Rê | 2 thăng | 1 giáng |
| La | 3 thăng | 0 |
| Si♭ | 2 giáng | 5 giáng |
| Mi♭ | 3 giáng | 6 giáng |

### Hợp âm có mặt trước Viterbi

`plan_markov_chords` chấm từng hợp âm bằng `bar_quantization_loss` trên chính `pitch_classes` của hợp âm đó. Catalog của chương thứ phải là hợp âm thứ ngay từ vòng này. Đổi tên sau khi Viterbi đã chọn sẽ để `C`, `F`, `Am`, `Em` mang Mi tự nhiên và La tự nhiên, trong lúc giai điệu đang hát Mi♭ và La♭, nên loss đẩy cả bài về Sol bảy hoặc Rê thứ.

Bậc chức năng lấy xác suất từ bảng chuyển gốc hiện có. Hàng của Đô dùng cho Đô thứ, hàng của Fa dùng cho Fa thứ, hàng của La thứ dùng cho La giáng, hàng của Mi thứ dùng cho Mi♭, hàng của Rê thứ dùng cho `Dm7♭5`, hàng của Sol giữ cho Sol và Sol bảy.

| Chức năng | Hợp âm trong catalog thứ |
|---|---|
| i | Đô thứ, Đô thứ bảy |
| iv | Fa thứ, Fa thứ bảy |
| ii° | `Dm7♭5` (`D–F–A♭–C`) |
| V | Sol, Sol bảy |
| ♭VI | La giáng, La giáng trưởng bảy |
| ♭III | Mi♭, Mi♭ trưởng bảy |
| đi qua, một ô, trước Sol | Fa♯ giảm bảy |

Đô thứ và Đô thứ bảy hạ bậc ba của Đô trưởng. Bậc bảy của Đô thứ bảy là Si♭. `Dm7♭5` thay Rê thứ và Rê thứ bảy: bậc 5 là La♭, cùng âm với thang, và nối `ii°7–V7–i`. Rê thứ (`D–F–A`) để La tự nhiên chồng lên La♭ của giai điệu.

`E7` và `A7` không có trong catalog thứ. `E7` là dominant của La thứ. Sau khi La thứ thành La giáng, `E7` đi tới La giáng là sai chức năng. `A7` mang Đô♯. `D7` mang La tự nhiên, nên cũng ở ngoài catalog. Fa♯ giảm bảy chỉ được một ô ngay trước Sol hoặc Sol bảy, cùng cửa với hợp âm đi qua hiện tại.

`_ROOT_REGIME_BIAS["downtrend"]` phạt Đô và Sol ở `0.35` vì bảng đó lấy La thứ làm chủ âm. Chương thứ lấy Đô thứ làm i và Sol làm V, nên không dùng hàng phạt đó. Bias gốc của chương thứ, số nhỏ là được ưu tiên:

| Gốc | Hợp âm | Bias |
|---|---|---|
| Đô | Đô thứ, Đô thứ bảy | 0,00 |
| Fa | Fa thứ, Fa thứ bảy | 0,04 |
| Sol | Sol, Sol bảy | 0,04 |
| La giáng | La giáng, La giáng trưởng bảy | 0,06 |
| Mi♭ | Mi♭, Mi♭ trưởng bảy | 0,06 |
| Rê | `Dm7♭5` | 0,06 |

Regime vẫn đổi màu câu: uptrend nghi về i và V, downtrend nghi về iv, ♭VI và ♭III. Cả ba regime đều để i và V ở bias thấp.

### Thang giai điệu

`raw_pitches` của chương thứ đi trên Đô thứ tự nhiên: Đô, Rê, Mi♭, Fa, Sol, La♭, Si♭. Bước liền bậc không có quãng 2 tăng La♭–Si. Giá đi qua bậc 6 và bậc 7 vẫn là một bước thang.

`quantize_strong_beats` và `bar_quantization_loss` nâng bậc 7 từ Si♭ lên Si tự nhiên chỉ trên ô có hợp âm Sol hoặc Sol bảy. Ô Đô thứ, Fa thứ, La giáng và Mi♭ hát Si♭. Ô Sol hát Si, nên cadence V–i còn âm dẫn, và Si không chọi Si♭ của Đô thứ bảy hay Mi♭. Nốt giữ xuyên vạch từ ô Sol sang ô chủ âm được tách, vì Si và Si♭ là hai cao độ.

`flute_harmony_pitch` dựng thang mở rộng bằng cách lặp pitch class của `scale` đang soạn qua các quãng 8. Hôm nay hàm gọi `c_major_scale`, nên sáo chương thứ thổi Mi tự nhiên và La tự nhiên lên trên violin đang hát Mi♭ và La♭. Trên ô Sol, thang mở rộng của ô đó dùng Si tự nhiên thay Si♭.

## Jazz ở mode thứ

`jazz_chord` tra `JAZZ_VOICING_BY_NAME` theo tên, rồi rơi xuống `JAZZ_CHORD_BY_ROOT` theo chữ cái gốc. Đô thứ có `root_step` là Đô, nên không có tên riêng thì nó thành Đô trưởng chín, mang Mi tự nhiên và Si tự nhiên. Ambient gọi cùng `jazz_chord` qua `promote_ambient_slots`.

Thêm `Cm9` (`C–E♭–G–B♭–D`, MIDI `60, 63, 67, 70, 74`). Đăng ký `"Cm"` và `"Cm7"` vào `JAZZ_VOICING_BY_NAME` trỏ tới `Cm9`. `"Fm"` đã trỏ `Fm9`. `"Fm7"` trỏ cùng `Fm9`. `"Dm7b5"` có mục riêng và không rơi xuống `DM9`, vì `DM9` mang La tự nhiên.

`_sax_melody_curve` đang gọi `c_major_scale`. Cao độ Mi♭ hoặc La♭ làm `scale.index` văng `ValueError`. `_walking_bass_bar` lấy nốt dẫn từ `c_major_scale(33, 60)`, nên bước qua Mi tự nhiên và La tự nhiên. `render_jazz_score` nhận thang của chương. Sax, vibraphone và walking bass dùng thang đó. Ô Sol trong bài thứ dùng thang của ô đó, có Si tự nhiên.

Bridge của head, ballad và finale nằm ở `plan_markov_chords`, trên catalog đúng mode:

- Phách đầu câu của đoạn giữa thưởng `PHRASE_TONIC_BONUS` cho bậc IV. Bài trưởng là Fa và Fa trưởng bảy. Bài thứ là Fa thứ và Fa thứ bảy. Đoạn giữa là câu tương phản 24 ô của chương I và IV, 16 ô giữa của chương II trong 1M, và câu giữa của ballad 3M.
- Hai ô cuối của đoạn đó hạ cost của Sol và Sol bảy.
- Phách đầu câu hát trở lại thưởng lại bậc I.

Bài ngắn không mở bridge sang một giọng thứ tư.

## Pedal của ambient

Halo, swell, shimmer và kính đọc `chord_at` của từng ô, nên màu hợp âm vẫn đổi. Drone của đoạn giữa giữ một nốt: `bass_midi` của chủ âm chương, trong không gian Đô là nốt gốc bậc I ở quãng 8 của bass. Fa trưởng chín, Rê thứ chín, La giáng trưởng bảy hoặc Sol chín đứng trên nốt Đô thành hợp âm slash. Intro, câu ngoài đoạn giữa, và outro vẫn để drone theo gốc hợp âm của ô, và các ô đạp đó là bậc I.

## Chỗ sửa trong code

- `prepare_month` và `prepare_quarter` nhận variant, cùng đường với `plan_span(symbol, span, variant)` ở kế hoạch nhịp. Giao hưởng và ambient gán mọi chương bằng giọng nhà. Jazz 1M chỉ đưa chương III lên một bước của vòng. Jazz 3M giữ giọng nhà. Tối giản gọi `month_keys` và `quarter_keys` như cũ.
- Mỗi `PreparedMovement` có `mode`, mặc định trưởng. Fingerprint cache thêm mode. File trưởng đã render không dùng cho chương thứ của cùng mã.
- `plan_markov_chords` nhận mode và nhận thang. Chương thứ dựng catalog ở bảng trên trước vòng Viterbi. Xác suất chuyển chép theo bậc chức năng. Bias gốc dùng bảng chương thứ. Intro, outro và thưởng phách đầu câu dùng Đô thứ và Đô thứ bảy cho mọi regime.
- Bridge jazz thưởng bậc IV ở phách đầu đoạn giữa, và hạ cost Sol cùng Sol bảy ở hai ô cuối đoạn.
- `raw_pitches` chương thứ là Đô thứ tự nhiên. Lượng tử hóa nâng Si chỉ trên ô Sol và Sol bảy.
- `flute_harmony_pitch` mở rộng đúng `scale` của chương. `render_jazz_score` đưa thang đó vào sax và walking bass.
- `Cm9` và `Dm7♭5` có mặt trong voicing jazz theo tên. `jazz_chord` của Đô thứ ra `Cm9`.
- Drone ambient ở đoạn giữa giữ `bass_midi` của chủ âm chương.
- MusicXML lấy `fifths` từ mode. `semitones` và `compose_register` vẫn theo giọng nhà. `_diatonic` của chương thứ là thứ tự nhiên. Si trên ô Sol lấy chính tả từ hợp âm.

## Thứ tự làm

1. Thêm `mode` trên movement và trên fingerprint. Giao hưởng và ambient gán mọi chương bằng giọng nhà. Jazz 1M giữ giọng nhà ở chương I, II, IV và bước vòng ở chương III. Tối giản giữ test ba giọng khác nhau.
2. Dựng catalog thứ, bias và thang thứ tự nhiên. Viterbi chấm trên `pitch_classes` của catalog đó. Chủ âm đạp là Đô thứ.
3. Nâng Si trên ô Sol. Sáo, sax và walking bass đọc thang chương. Voicing jazz của Đô thứ là `Cm9`.
4. Bridge jazz và pedal drone của đoạn giữa ambient.
5. Nghe một mã giọng Đô và một mã giọng Rê: tháng bốn tuần tăng, tháng có một tuần giảm, quý có tháng giữa giảm. Nghe ballad jazz thứ và một chương ambient thứ.

## Kiểm tra

- Giao hưởng 1M của VNM là bốn chương, cùng `semitones` 0. Chương selloff có hóa biểu 3 giáng. Chương rally có hóa biểu 0.
- Giao hưởng 1M của FPT là bốn chương Rê. Không có chương La và không có chương Đô. Chương selloff có hóa biểu 1 giáng.
- Giao hưởng 3M chỉ khác mode ở chương nào có tính cách selloff hoặc volatile kết bằng downtrend.
- Jazz 1M của VNM: chương I, II và IV cùng `semitones` 0. Chương III là Rê khi tuần đó tăng, Si♭ khi tuần đó giảm hoặc đi ngang. Bridge của ballad thưởng cho Fa khi bài trưởng, và cho Fa thứ khi bài thứ. Hai ô cuối bridge ưu tiên Sol hoặc Sol bảy. Câu hát trở lại về Đô.
- Ambient 1M và 3M của cùng mã dùng một `semitones` cho mọi chương. Drone của đoạn giữa là một nốt, đúng `bass_midi` của chủ âm chương. Halo của ô đó vẫn đổi theo hợp âm.
- Tối giản 1M vẫn ba giọng trong ba chương đầu, đúng `month_keys`.
- Intro và outro của chương trưởng là Đô hoặc Đô trưởng bảy, kể cả regime downtrend.
- Intro và outro của chương thứ là Đô thứ hoặc Đô thứ bảy. Sau khi dịch, FPT nghe Rê thứ.
- Viterbi của chương thứ đọc `pitch_classes` có Mi♭ và La♭. `Dm7♭5` có La♭. Catalog thứ không có `E7`, `A7`, `D7`, Rê thứ.
- Bias của Đô và Sol trong chương thứ là 0,00 và 0,04. Hàng `downtrend` phạt 0,35 không áp vào chương thứ.
- `raw_pitches` chương thứ là bảy âm Đô thứ tự nhiên. Ô Sol lượng tử hóa bậc 7 thành Si. Ô Đô thứ giữ Si♭.
- `jazz_chord` của Đô thứ là `Cm9`. Sax của bài thứ nhận thang có Mi♭ mà không văng `ValueError`.
- `flute_harmony_pitch` của chương thứ không trả Mi tự nhiên hay La tự nhiên khi giai điệu đang ở Mi♭ hoặc La♭.
- Một câu sideway chương trưởng còn hợp âm La thứ ở giữa câu. Phách đầu câu không phải La thứ.
- 1Y của mọi dạng vẫn đổi giọng theo mùa. 1D và 1W vẫn một giọng.
