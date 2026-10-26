# Máy đo chấm điểm sonify

Phương án chấm phần máy đo. Người đo nghe sau, trên cùng một rổ, và không cộng vào vector.

Máy đọc bản ký hiệu (`Score` / MusicXML) và đối chiếu với nến nguồn. File WAV để ở một phép kiểm phát riêng: MuseSounds bỏ qua velocity của nhiều nhạc cụ, nên mức nghe được không phải hợp đồng mã hóa. Các hằng số dưới đây lấy từ `backend/app/sonify/` tại thời điểm viết tài liệu: `quantize.py`, `dynamics.py`, `chords.py`, `keys.py`, `form.py`, `playback.py`.

## 1. Sản phẩm công bố

Mỗi bản cho ra ba khối:

| Khối | Ý nghĩa |
|---|---|
| Cổng | Đạt hoặc trượt. Trượt là lỗi hợp đồng. |
| Trung thực | Phần hình giá và thanh khoản còn lại sau lượng tử hóa. |
| Hợp lệ | Ngữ pháp đếm được: âm hợp âm, dẫn giọng, độ nhàm có điều kiện. |

Điểm công bố là bộ ba này. Một tổng có trọng số chỉ xuất hiện sau khi có tập nghe đóng băng. Trước đó trọng số là chính sách, chưa phải phép đo.

`bar_quantization_loss` trong `quantize.py` đứng ngoài vector. Đó là mục tiêu planner đang tối thiểu. `research/sonify/harmony_benchmark.py` so số nốt bị bẻ giữa Markov và vòng lặp cố định. Việc đó chẩn đoán planner. F1 và F3 dưới đây đo giai điệu đã viết so với giá.

## 2. Kênh máy được chấm

Giá được kéo min–max vào thang của riêng bản đó (`price_to_scale_index`). Một phiên 0,4% và một phiên sát biên độ trần sàn có thể cùng trải hết register. Cỡ bước nhảy mang hình trong phiên. Biên độ lợi suất nằm ở character và ở thanh khoản.

| Kênh | Nguồn | Chỗ mất thông tin | Máy đo |
|---|---|---|---|
| Contour giá | `price_to_scale_index`, rồi snap phách mạnh vào âm hợp âm | Viterbi có thể bẻ ngược hướng. `CONTOUR_WRONG_WAY_PENALTY` là chi phí, không phải lệnh cấm | Giai điệu đã viết so với chỉ số thang thô |
| Thanh khoản | `average_liquidity`, clip `4 ×` median, log, p10–p90, `marking_for_volume` | `high/low < 2` thì mọi cửa sổ là `mf`. `piano_marking` gập `mf`/`f` về `mp` và `p`/`mp` về `p`. Bass trần ở `mp`. Groove `chamber` / `half` hạ thêm | Spearman trên `score.liquidity` |
| Regime | MA20, băng `0,15%`, `REGIME_BIAS` là chi phí (thấp = được ưu tiên) | Bias là một số hạng. Thua quantization loss và xác suất chuyển thì regime không còn trên bản viết | Chi phí bias của hợp âm đã chọn, so với catalog và so với regime bị xáo |
| Character | `movement_character`, `movement_mode`, `_CHARACTER_BAR_CHANGE` | Mode là hàm tất định của character. Phạt đổi hợp âm (`volatile` `0,45`, `calm` `0,80`, `rally`/`selloff` `0,60`) có thể quá yếu để nghe | Mode là cổng hồi quy. Tốc độ đổi hợp âm chỉ đọc trên cả rổ, tách theo nhãn |
| Khung và danh tính | Giọng nhà theo mã. Nhịp theo lịch khung. Warm-up và cool-down đạp chủ âm | Cố ý không mang đường giá | Hợp đồng khung: chủ âm, động lực lắng về `ppp` |

`_ROOT_REGIME_BIAS` trong `chords.py`: uptrend ưu tiên `C` (chi phí `0`), phạt `A` `0,35` và `E` `0,45`. Downtrend ưu tiên `A`, phạt `C` và `G` `0,35`. Sideway ưu tiên `C`.

## 3. Đồng hồ

Giai đoạn 1 dùng bản ngày, giao hưởng, `4/4`. `playback.py` khóa 34 ô: ô `0–1` warm-up, ô `2–31` thân giá, ô `32–33` cool-down. Contour và thanh khoản của thân chỉ đọc ô `2–31`. Hai đầu khung chỉ vào M5.

Phách mạnh lấy từ meter của variant. Ở `4/4` đó là móc `0` và `4` (`STRONG_BEAT_EIGHTHS`). Giai điệu là bè lead. Giao hưởng dùng violin. Nghỉ thì giữ nốt đang ngân cho contour, và loại móc nghỉ khỏi tỷ lệ âm hợp âm.

Các variant và nhịp khác (`6/8`, `5/4`, `7/8`, `12/8`, `6/4`, `3/4`) đổi vị trí phách mạnh và đổi bè lead. Chúng nằm sau giai đoạn 1. Chỉ số dùng cùng định nghĩa, với meter và lead truyền vào.

## 4. Vector trung thực

`r` là chỉ số thang của giá thô, trước snap. `m` là chỉ số thang của lead đã viết. Cùng thang renderer đã dùng, kể cả thang thứ tự nhiên và Si nâng trên ô `G` / `G7`.

| Mã | Cách tính | Bỏ qua khi | Cách đọc |
|---|---|---|---|
| F1 hướng | Tỷ lệ bước mà dấu `Δr` và dấu `Δm` trùng nhau. Bỏ bước một trong hai bên đứng yên | Dưới 3 bậc thang khác nhau trong thân | `1` bám hướng. Quanh `0,5` mất contour. Âm là đi ngược |
| F2 mức | Spearman(`r`, `m`) trên phách mạnh | Cùng điều kiện ít bậc thang | Khớp thứ hạng trong phiên. Không đo phần trăm lợi suất |
| F3 độ bẻ | Trung bình `\|m − r\|` trên phách mạnh, đơn vị bậc thang | Luôn báo | Hòa âm bẻ ít khi số này giảm. Đi cùng F1 |
| F4 điểm ngoặt | Recall cực trị giá nổi ít nhất 1 bậc thang, khớp cực trị giai điệu cùng hướng trong ±1 ô | Thân không có cực trị nổi | Bắt đỉnh và đáy. Tương quan suôn có thể bỏ đúng chỗ tai nhận ra |
| F5 thanh khoản | Spearman giữa volume cửa sổ (`average_liquidity`) và hạng `p < mp < mf < f` của `score.liquidity` | `high/low < MIN_SPAN_RATIO` (`2`). Cổng yêu cầu mọi cửa sổ là `mf` | Chữ piano và velocity bass đứng ngoài số này |
| F6 regime | Chi phí `REGIME_BIAS` trung bình của hợp âm đã chọn, trừ chi phí trung bình catalog. Đối chứng xáo nhãn regime trên cùng bản | Ô pedal ngoài thân giá | Lift dương, và đối chứng làm lift tụt, thì kênh còn sống. Lift cao cả khi xáo nhãn nghĩa là hợp âm không phân biệt regime |

Phiên dưới 3 bậc thang: bỏ F1, F2, F4. Cổng yêu cầu giai điệu thân không vượt 2 bậc thang. Bản nhạc của một băng giá phẳng ở yên trong một vùng hẹp.

## 5. Vector hợp lệ

Các số này phát hiện bản gãy hoặc bản lì. Ngưỡng entropy và độ dài hợp âm lấy theo phân vị của rổ, trong cùng character và cùng variant.

| Mã | Đối tượng | Điều kiện character |
|---|---|---|
| M1 âm hợp âm | Tỷ lệ phách mạnh của lead nằm trong pitch class hợp âm của ô, đúng thang | Cổng. Renderer cam kết snap thì một lần trượt là lỗi |
| M2 dẫn giọng | Bước bass quá quãng 8. Bước giai điệu quá quãng 8 không được bước ngược liền sau. Quãng 5 song song lead–bass trên phách mạnh | Cùng ngưỡng mọi character |
| M3 âm chung | Khi đổi hợp âm, số pitch class giữ lại. Báo trung bình và tỷ lệ lần đổi không chung âm | Volatile được đổi dày. Calm bị trừ khi đổi liên tục mà không chung âm |
| M4 nhàm có điều kiện | Entropy bigram pitch-class của lead, hợp âm dài nhất, số chữ dynamic khác nhau | Calm, và volume-span dưới `2×`, được một hợp âm và một chữ `mf`. Volatile, hoặc bản từ `1M` trở lên, mà một hợp âm chiếm phần lớn thân là lỗi |
| M5 khung | Warm-up mở nhỏ hơn thân. Cool-down tới `ppp`. Ô pedal giữ chủ âm | Hợp đồng khung |

Mode khác `movement_mode(character, closing)` là cổng hồi quy. Nó xác nhận hàm đã chạy. Nó không cộng vào trung thực.

## 6. Khi một thay đổi của renderer được nhận

So trên một rổ đóng băng, tách tầng `variant × span × character`. Trung bình một phiên calm với một phiên sát biên độ làm mất tầng đang hỏng.

1. Mọi bản vẫn qua M1, vùng âm, phủ nến thân, M5, hợp đồng phiên phẳng, và hợp đồng volume-span dưới `2×`. Một cổng gãy thì bản mới dừng lại.
2. Trung vị F1 của rổ giảm không quá `0,02`.
3. Ít nhất một trung vị khác cải thiện quá biên đã đăng ký trước khi chạy: F3 giảm, F5 tăng, F6 tăng, hoặc một chỉ số M2–M4 đỡ hơn.
4. Không có tầng nào đi ngược quá biên đó.

## 7. Bản đối chứng

Mỗi chỉ số phải đổ khi đúng kênh của nó bị phá. Chỉ số đứng yên thì bỏ chỉ số đó.

| Phá | Kỳ vọng |
|---|---|
| Đảo chuỗi giá, giữ volume và nhịp | F1 đổi dấu hoặc tụt mạnh. F5 đứng |
| Đảo volume, giữ giá | F5 đổi dấu. F1 đứng |
| Xáo nhãn regime | F6 lift về gần `0` |
| Giữ nhịp, hoán vị cao độ lead | F1 và M1 đổ |

F1 đứng sau khi đảo giá nghĩa là chỉ số đang đo hình cố định của style. F6 đứng sau khi xáo regime nghĩa là kênh regime đã chết trên bản viết, dù code vẫn cộng bias.

## 8. Giai đoạn 1

Phạm vi: `1D`, giao hưởng, `4/4`, lead violin, thân ô `2–31`.

Mỗi phiên ghi một bản:

- `gates`
- F1–F6
- M1–M5
- tầng: variant, span, character, số bậc thang phân biệt, volume span ratio

Ba bản đối chứng sinh từ cùng nến: giá đảo, volume đảo, regime xáo. In cạnh bản thật.

Bốn JSON trong `research/sonify/out` là hạt giống. Chúng chưa đủ để khóa ngưỡng mềm của M3 và M4. Ngưỡng cổng khóa được ngay, vì chúng là bất biến của renderer.

Chưa làm trong giai đoạn này: tổng có trọng số, guitar và jazz, nhịp khác `4/4`, bản `1W`–`1Y`, chấm WAV. Ô 32 của `1W` (cầu nối qua đêm) khi tới lượt sẽ ra khỏi F1. Ô đó cố ý lấy giá mở phiên sau.

## 9. Người đo

Người đo nghe mù, không thấy số, trên đúng rổ đóng băng.

Hai việc:

1. Gán phiên vào một trong bốn ô: tăng, giảm, ngang, đảo. Đối chiếu với F1 và F4 để biết máy có đo cái tai bắt được hay không.
2. Đánh dấu ô nghe giả hoặc gãy. Chỗ nhiều người cùng đánh dấu mà vector không thấy thì thêm một chỉ số. Chỗ người nghe không đồng thuận thì để ngoài máy.

Người đo trả lời hai việc đó. Một thang 1–10 rồi hồi quy ra trọng số sẽ biến một vòng nghe thành định nghĩa của máy.
