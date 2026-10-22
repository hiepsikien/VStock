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

Hợp âm đi qua trong câu giữ nguyên chức năng: Rê thứ là bậc ii, Sol là bậc V, Fa là bậc IV. Những hợp âm đó không phải chủ âm mới.

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

Hóa biểu là thứ cùng tên của giọng nhà. Dịch cao độ giữ nguyên.

| Giọng nhà | Hóa biểu trưởng | Hóa biểu thứ cùng tên |
|---|---|---|
| Đô | 0 | 3 giáng |
| Rê | 2 thăng | 1 giáng |
| La | 3 thăng | 0 |
| Si♭ | 2 giáng | 5 giáng |
| Mi♭ | 3 giáng | 6 giáng |

Giai điệu của chương thứ lượng tử trên thang Đô thứ hòa thanh: Đô, Rê, Mi♭, Fa, Sol, La♭, Si. Si trưởng là âm dẫn của Sol trưởng, nên cadence V–i còn lực kéo. Nốt Si đó viết theo hợp âm khi hợp âm là Sol hoặc Sol bảy. Các nốt còn lại viết theo hóa biểu thứ tự nhiên.

Markov vẫn chạy trên bảng chuyển hiện có. Một lớp đổi tên chạy sau đó, trên mọi chương đang ở mode thứ:

| Hợp âm Markov | Hợp âm nghe |
|---|---|
| Đô, Đô trưởng bảy | Đô thứ, Đô thứ bảy |
| Fa, Fa trưởng bảy | Fa thứ, Fa thứ bảy nếu đã có, không thì Fa thứ |
| La thứ, La thứ bảy | La giáng, La giáng trưởng bảy |
| Mi thứ, Mi thứ bảy | Mi giáng, Mi giáng trưởng bảy |
| Sol, Sol bảy | giữ nguyên, bậc V hòa thanh |
| Rê thứ, Rê thứ bảy | giữ nguyên, bậc ii |
| Các dominant phụ, hợp âm mượn còn lại | giữ nguyên |

Đô thứ và Đô thứ bảy là hai hợp âm mới: bậc ba của Đô trưởng hạ xuống một semitone, bậc bảy của hợp âm bảy là Si giáng. Chúng chỉ đứng ở vị trí chủ âm của chương thứ. Chương trưởng không chọn chúng.

Sau lớp đổi tên, sideway trong chương thứ thành Đô thứ xen La giáng, tức i–VI. Sideway trong chương trưởng vẫn là Đô xen La thứ, tức I–vi, và phách đầu câu vẫn về Đô.

## Chỗ sửa trong code

- `prepare_month` và `prepare_quarter` nhận variant, cùng đường với `plan_span(symbol, span, variant)` ở kế hoạch nhịp. Giao hưởng và ambient gán mọi chương bằng giọng nhà. Jazz 1M chỉ đưa chương III lên một bước của vòng. Jazz 3M giữ giọng nhà. Tối giản gọi `month_keys` và `quarter_keys` như cũ.
- Mỗi `PreparedMovement` có `mode`, mặc định trưởng. Fingerprint cache thêm mode. File trưởng đã render không dùng cho chương thứ của cùng mã.
- `plan_markov_chords` nhận mode. Intro, outro và thưởng phách đầu câu dùng cặp chủ âm của mode, cho mọi regime. Hôm nay đoạn downtrend thưởng cho `tonic("downtrend")`, tức La thứ. Riêng bridge của jazz head, ballad và finale thưởng cho bậc IV, và hai ô cuối bridge ưu tiên bậc V của giọng bài.
- Lớp đổi tên hợp âm chạy sau Markov, trước `transpose_chord` và trước khi viết nốt.
- Thang giai điệu của chương thứ là Đô thứ hòa thanh. `quantize_strong_beats` đọc thang đó. Chương trưởng vẫn là Đô trưởng.
- MusicXML lấy `fifths` từ mode. `semitones` và `compose_register` vẫn theo giọng nhà, nên chương thứ không hạ trần violin thêm một lần nữa.
- `_diatonic` của chương thứ dùng các bậc thứ tự nhiên để viết nốt trong hóa biểu. Âm dẫn Si lấy chính tả từ hợp âm Sol.

## Thứ tự làm

1. Thêm `mode` trên movement và trên fingerprint. Giao hưởng và ambient gán mọi chương bằng giọng nhà. Jazz 1M giữ giọng nhà ở chương I, II, IV và bước vòng ở chương III. Tối giản giữ test ba giọng khác nhau.
2. Chủ âm đạp và thưởng phách đầu câu theo mode. Chương trưởng hết lấy La thứ làm gốc của đoạn giảm.
3. Thêm Đô thứ, Đô thứ bảy, và lớp đổi tên. Hóa biểu và thang thứ hòa thanh chỉ bật khi mode là thứ.
4. Nghe một mã giọng Đô và một mã giọng Rê: tháng bốn tuần tăng, tháng có một tuần giảm, quý có tháng giữa giảm.

## Kiểm tra

- Giao hưởng 1M của VNM là bốn chương, cùng `semitones` 0. Chương selloff có hóa biểu 3 giáng. Chương rally có hóa biểu 0.
- Giao hưởng 1M của FPT là bốn chương Rê. Không có chương La và không có chương Đô. Chương selloff có hóa biểu 1 giáng.
- Giao hưởng 3M chỉ khác mode ở chương nào có tính cách selloff hoặc volatile kết bằng downtrend.
- Jazz 1M của VNM: chương I, II và IV cùng `semitones` 0. Chương III là Rê khi tuần đó tăng, Si♭ khi tuần đó giảm hoặc đi ngang. Bridge của ballad thưởng cho Fa khi bài trưởng, và cho Fa thứ khi bài thứ. Câu hát trở lại về Đô.
- Ambient 1M và 3M của cùng mã dùng một `semitones` cho mọi chương. Đoạn giữa không đổi gốc pedal.
- Tối giản 1M vẫn ba giọng trong ba chương đầu, đúng `month_keys`.
- Intro và outro của chương trưởng là Đô hoặc Đô trưởng bảy, kể cả regime downtrend.
- Intro và outro của chương thứ là Đô thứ hoặc Đô thứ bảy. Sau khi dịch, FPT nghe Rê thứ.
- Một câu sideway chương trưởng còn hợp âm La thứ ở giữa câu. Phách đầu câu không phải La thứ.
- Giai điệu chương thứ chỉ dùng bảy âm của Đô thứ hòa thanh, rồi dịch theo giọng nhà.
- 1Y của mọi dạng vẫn đổi giọng theo mùa. 1D và 1W vẫn một giọng.
