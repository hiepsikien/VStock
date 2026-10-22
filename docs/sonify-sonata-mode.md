# Chủ âm của sonata giao hưởng

Kế hoạch cho giọng của giao hưởng 1M và 3M. Nhịp và khung chương nằm ở `docs/sonify-meter-frame.md`. 1D, 1W, 1Y và ba dạng Jazz, Tối giản, Ambient giữ cách chọn giọng hiện tại.

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

Jazz, Tối giản và Ambient của 1M và 3M vẫn gọi `month_keys` và `quarter_keys`. 1Y của giao hưởng vẫn đi theo mùa trên vòng giọng, vì tổ khúc bốn mùa lấy việc đổi giọng làm màu của từng mùa.

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

Markov vẫn chạy trên bảng chuyển hiện có. Một lớp đổi tên chạy sau đó, chỉ trên chương giao hưởng đang ở mode thứ:

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

- `prepare_month` và `prepare_quarter` nhận variant, cùng đường với `plan_span(symbol, span, variant)` ở kế hoạch nhịp. Giao hưởng gọi một hàm mode thay cho `month_keys` và `quarter_keys`. Ba dạng kia gọi hai hàm cũ.
- Mỗi `PreparedMovement` có `mode`, mặc định trưởng. Fingerprint cache thêm mode. File trưởng đã render không dùng cho chương thứ của cùng mã.
- `plan_markov_chords` nhận mode. Intro, outro và thưởng phách đầu câu dùng cặp chủ âm của mode, cho mọi regime. Hôm nay đoạn downtrend thưởng cho `tonic("downtrend")`, tức La thứ.
- Lớp đổi tên hợp âm chạy sau Markov, trước `transpose_chord` và trước khi viết nốt.
- Thang giai điệu của chương thứ là Đô thứ hòa thanh. `quantize_strong_beats` đọc thang đó. Chương trưởng vẫn là Đô trưởng.
- MusicXML lấy `fifths` từ mode. `semitones` và `compose_register` vẫn theo giọng nhà, nên chương thứ không hạ trần violin thêm một lần nữa.
- `_diatonic` của chương thứ dùng các bậc thứ tự nhiên để viết nốt trong hóa biểu. Âm dẫn Si lấy chính tả từ hợp âm Sol.

## Thứ tự làm

1. Thêm `mode` trên movement và trên fingerprint. Giao hưởng 1M và 3M gán mọi chương bằng giọng nhà. Ba dạng kia giữ test ba giọng khác nhau.
2. Chủ âm đạp và thưởng phách đầu câu theo mode. Chương trưởng hết lấy La thứ làm gốc của đoạn giảm.
3. Thêm Đô thứ, Đô thứ bảy, và lớp đổi tên. Hóa biểu và thang thứ hòa thanh chỉ bật khi mode là thứ.
4. Nghe một mã giọng Đô và một mã giọng Rê: tháng bốn tuần tăng, tháng có một tuần giảm, quý có tháng giữa giảm.

## Kiểm tra

- Giao hưởng 1M của VNM là bốn chương, cùng `semitones` 0. Chương selloff có hóa biểu 3 giáng. Chương rally có hóa biểu 0.
- Giao hưởng 1M của FPT là bốn chương Rê. Không có chương La và không có chương Đô. Chương selloff có hóa biểu 1 giáng.
- Giao hưởng 3M chỉ khác mode ở chương nào có tính cách selloff hoặc volatile kết bằng downtrend.
- Jazz 1M của cùng mã vẫn ba giọng trong ba chương đầu, đúng `month_keys`.
- Intro và outro của chương trưởng là Đô hoặc Đô trưởng bảy, kể cả regime downtrend.
- Intro và outro của chương thứ là Đô thứ hoặc Đô thứ bảy. Sau khi dịch, FPT nghe Rê thứ.
- Một câu sideway chương trưởng còn hợp âm La thứ ở giữa câu. Phách đầu câu không phải La thứ.
- Giai điệu chương thứ chỉ dùng bảy âm của Đô thứ hòa thanh, rồi dịch theo giọng nhà.
- 1Y giao hưởng vẫn đổi giọng theo mùa. 1D và 1W vẫn một giọng.
