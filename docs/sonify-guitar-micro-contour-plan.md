# Vi mô trong ô: móc đơn, móc kép, phách mạnh

> **Trạng thái**: đã hát. Renderer của mục 5 đã có vi mô.
> **Mốc đã hát**: Galop 1 và Galop 2 trong `backend/app/sonify/guitar_sor.py`, khóa ở mục 4.4 của [`docs/sonify-guitar-gavotte-galop.md`](./sonify-guitar-gavotte-galop.md).
> **Phạm vi đợt sau**: thân bài Sor, Bach, Villa-Lobos, Barrios, Brouwer. Cửa intro/outro, profile sóng, cổng snap, và `select_scale_plan` đứng ngoài.

Galop nghe rõ hơn vì trong một ô các hình nốt không còn cùng một lực. Bậc là `_GALOP_STEP = 2`. Bốn bậc bằng một bậc chữ. Cả ô đo từ một mức V, mức lead viết cao nhất. Móc đơn Galop 1 tại `0, 1, 2, 3` là `V−6, V−4, V−2, V`. Trong một phách, móc kép đầu thấp hơn móc đơn 2, móc kép sau thấp hơn 4. Galop 2 lấy quãng 12 của nửa sau làm đỉnh. Bass đi cùng móc đơn của phách đó.

Câu phi dâng về cuối ô là của *Galop* Op. 32 No. 6. Điệu khác giữ nhịp của điệu đó. Đơn vị nghe vẫn là bậc 2, vì sóng cộng một tâm cho cả ô và humanize để yên bậc thang 1 hoặc 2. Bậc 1 chìm. Bậc 4 đã là một chữ.

---

## 1. Luật chung khi viết

`_shape_accompaniment` ghi đè vận tốc bass và bè trong bằng `_under_lead`. Mọi bậc của hai bè đó gắn **sau** lần gọi này, cùng chỗ `_contour_galop1` đang đứng. Lead của Bach không đi qua hàm đó, nên bậc của lead có thể gắn lúc tạo nốt.

Hạ nốt yếu. Giữ nốt mạnh ở mức đã viết. Nốt viết trên 64 đi vào cửa móng. Nâng phách mạnh sẽ biến một nốt ấm thành snap.

Sàn là 40. Sau khi hạ, thứ tự trong một tiếng vẫn là lead > bass > bè trong, mỗi cặp cách ít nhất 2. Đầu `guitar_bach.py`, `guitar_sor.py` và `guitar_brouwer.py` gán `_BASS = 56`, `_INNER = 46`, rồi import đè từ `guitar_patterns`. Hằng số sống là của `guitar.py`: `_BASS = 60`, `_INNER = 56`. `_under_lead(64, "mf")` ra bass 60, bè trong 56. Khoảng lead–bass ở `mf` là 4. Bậc 2 còn chỗ. Bậc 4 chạm bè dưới. Ở `f`, bass đã là `lead − 2`. Hết chỗ thì bỏ bậc của riêng lead, hoặc hạ cả ba bè cùng một số khi cả ba là một hình nốt. Câu hát đã viết 4 đến 8 vẫn lớn hơn bậc vi mô: nốt đỉnh câu giữ đỉnh.

`_shape_dynamics` chạy sau renderer, trước sóng. Extra của câu đang lên cộng theo từng móc, và extra đó xóa bậc trong ô. Mọi pattern nhận contour ở mục 5 đi cùng nhánh Galop: một extra cho cả ô, lấy ở móc đầu.

Passage scale thay lead trên eighth của passage và trồng lại bass trên `ctx.strong`. Bậc vi mô là phần ô passage không đè. Không đổi `select_scale_plan`. `_smooth_boundaries` và `_transitions` không san lực trong thân ô. Chúng có thể thay móc cuối ô biên bằng pickup sau khi renderer trả về.

Test khóa **hiệu trong ô**, cùng kiểu `test_galop_beats_keep_a_micro_velocity_contour`. Sóng dời cả ô bằng một số. Khóa số tuyệt đối sẽ gãy khi tâm ô đổi.

Hình lệch nằm trong pattern, cùng chỗ với lưới nốt và cờ staccato. Bourrée, Gavotte, tumbao, allemande và Galop mỗi điệu một hình. Pattern khai báo nốt nào lệch mấy bậc, và gọi contour ở cuối renderer của chính nó.

Chỉ cơ học đi vào `guitar_patterns.py`: `_MICRO`, sàn, `_micro_drop`, `_micro_fits`, `_micro_raise`. Đổi hạt nghe, hoặc siết khoảng lead–bass, sửa một chỗ. Galop giữ `_contour_galop1` và `_contour_galop2`. Hai hàm đó đo từ một đỉnh viết. Hạ theo vận tốc từng nốt sẽ để câu đang lên xóa khoảng trong phách.

Một pass cuối trong `render_patterned_voices` đứng xa nhịp nó mô tả, và chạy sai thứ tự. `_shape_accompaniment` ghi đè bass và bè trong, nên bậc của hai bè đó chỉ sống sau lần ghi đè. Mordent hạ nốt láy trước `_punch`, vì punch chỉ cộng vào móc kép đầu. Tumbao hạ cú giữa sau punch, để cú đầu vẫn là accent. Noviembre chạy sau `_soften_attack` và không đụng xung sau: test khóa xung đó cao hơn nốt lấy đà đúng 6.

---

## 2. Trường phái

**Sor, cổ điển Paris.** Méthode đòi ngón phải đều. Étude và cantabile sống ở sự đều và ở câu. Chỗ được lệch là nốt láy dưới nốt cấu trúc (biến tấu Op. 9), và hành khúc: nốt dài nặng, nốt ngắn nhẹ, phách 1 nặng hơn phách 3 (*Élégiaque*).

**Bach, suite Đức.** Quantz: nốt rơi đúng phách là nốt tốt, nốt lệch phách là nốt xấu. Một bậc 2. Không notes inégales: độ dài và cờ staccato giữ nguyên, chỉ đổi lực. Mỗi điệu một chỗ nhấn. Sarabande đã nhấn phách 2 bằng `_punch` +8. Fugue là bè hát, đều. Allemande là style brisé, thân bài đều. Nốt lấy đà và tirata mới là chỗ dâng.

**Villa-Lobos.** Tresillo là `3+3+2`, đã nhấn `{0, 3, 6}`. Hai étude đã có cung trong ô. Thêm câu phi châu Âu làm hỏng nhịp Brazil và làm hỏng étude.

**Barrios, lãng mạn Paraguay.** Chất nằm ở nhấn lệch phách và hemiola, đã có `sync` +4 cùng `accent`. Canto, andante, tremolo đi theo câu. Tremolo lệch giữa các cú lập sẽ vỡ tiếng rung. Vals vẫn là vũ khúc: bass phách 1 nặng hơn bass giữa, trong khi cú sync ở phách 2 giữ nguyên.

**Brouwer, hiện đại Cuba.** *Un día de noviembre* là ballad: nhịp đôi nhẹ, nốt lấy đà đã nhẹ hơn xung 6, quầng màu đều. Étude là tumbao `3+3+2`: ba cú ngón cái là trụ, cú cuối là nốt chờ sang ô sau, bè trong là máy đều. *Elogio* là ostinato staccato đều, và cú Bartók ở móc 3 đã là vết cắt. Sarabande tân cổ điển đã nhấn phách 2 và để swarm tự hairpin. Không phủ câu phi Galop, không phủ nốt tốt/xấu của Quantz lên tumbao.

---

## 3. Đã có vi mô, để yên

| Pattern | Chỗ đã viết | Vì sao giữ |
|---|---|---|
| `galop` | `_contour_galop1`, `_contour_galop2` | Mốc của đợt này |
| `etude1` | `_ETUDE1_ARC`: các móc cạnh hai nốt hát là `+2`, hai đầu ô là `−2` | Cung tay phải của Étude 1. Đỉnh là nốt hát |
| `etude11` | Cung sextuplet `−10, −6, −7, −10`, rồi `_ETUDE11_TILT` `−1, −1, 0, +1`. Móc đơn thứ hai của giai điệu là `hairpin − 8` | Máy đã có hướng trong phách. Nâng tilt lên 2 sẽ viết lại tế bào đã khóa |
| `villa_pattern` | `_accent_at`: tresillo `+8`, móc còn lại `−2` | Đúng `3+3+2`. Ô không tresillo giữ bè trong đều. Test khóa một mức cho ô đó |
| `preludio` | Móc chẵn hơn móc lẻ đúng 4 | Test `evens[0] - odds[0] == 4` |
| `tremolo` | Trong một phách, bốn cú lead lệch mốc `−6, −3, −4, −6`. Bass bốn phách lệch `−4, 0, 4, 1` | Test khóa cả hai dãy. Rung phải đều giữa các cú lập của một nốt |
| `choro`, `polca`, `hemiola` | `_dance_velocity(..., sync=True)` cộng 4 khi còn dưới lead | Nhấn lệch phách là chất. Hemiola đã to hơn phách viết. Nâng phách 1 sẽ xóa hemiola |
| `thumb_cantabile` | Câu hát ở ngón cái. Hợp âm dyad đã lệch nhau trong cửa `_INNER` | Cùng họ cantabile |
| `elogio_pizz` | Mọi cú staccato cùng mức sau shape. Móc đơn 3 được `_punch` +12, bass và bè trong | Ostinato phải đều thì cú Bartók mới là vết cắt. Test khóa slap lớn hơn phách 0. Thêm nốt tốt/xấu sẽ biến điệu thành vũ khúc có phách 1 |
| `sarabande` Brouwer | Phách 2: `_punch` +8 trên bass và bè trong. Swarm đi `_swarm_velocities`, ramp tới nốt cuối | Hairpin của swarm là vi mô của câu lướt. Khía thêm móc kép lệch sẽ răng cưa ramp đó |

---

## 4. Giữ đều

| Pattern | Giữ | Lý do |
|---|---|---|
| `study` | Bass một mức, bè trong một mức | Étude của Sor luyện ngón đều. `test_arpeggio_families_alternate_inner_chord_tones` khóa `len(study_bass) == 1` và `len(study_inner) == 1`. Giai điệu đã có `_sustain` |
| `cantabile` | Câu và song thanh | W = 9. Bass là nốt dài. Chặt móc đơn làm gãy tiếng hát |
| `bach_fuga` | Đều trên chủ đề | Bè hát. Câu trả lời đã `_soften_attack` 8 ở ô vào |
| `andante`, `chord_melody` | Hợp âm khối một lực | Một tiếng. Câu đã có swell |
| Thân `bach_allemande` | Style brisé, không staccato | Allemande Đức đều. Chỉ nốt lấy đà bốn móc kép được dâng, mục 5 |
| Bass `bach_chaconne` | Hai nốt nền bằng nhau | Ostinato. Bariolage bè trong cũng đều, vì tiếng lập là kỹ thuật |
| Scale gigue và scale chaconne | Nốt đầu gigue, hoặc nốt cuối chaconne, giữ đỉnh đã viết | Snap đang trỏ vào đúng cú đó. Phần chạy còn lại giữ `_MELODY` |
| Quầng `noviembre` | Bè trong một mức | Arpeggio màu là quầng của ballad. Chặt móc đơn làm gãy *Un día de noviembre* |
| Máy `brouwer_etude` | Bè trong trên móc không có ngón cái, một mức | Étude Sencillo là motor. Nhịp Cuba nằm ở ba cú bass, không nằm ở việc làm yếu móc lệch |

---

## 5. Bậc mới

Bậc trong bảng là số lần `_MICRO = 2`, hạ khỏi mức nốt đó đang có sau `_note_velocity` hoặc sau `_shape_accompaniment`. `0` là giữ nguyên.

### 5.1. Bach, Bourrée — chỉ bass

Giai điệu là giá, `_sustain`. Nhịp điệu ở bass. `_render_bach_bourree_bar` gọi contour sau `_shape_accompaniment`. Hai nửa ô cùng một luật. Ô Bourrée đều, không dâng về cuối.

Hình đang có trong `test_bach_bourree_walks_under_a_hold_and_sits_under_a_running_treble`:

| Hình | Nốt | Bậc |
|---|---|---|
| Nốt đen mở đầu nửa ô, không staccato | phách của tế bào | 0 |
| Nốt đen staccato, khi giá chạy | phách đáp | −1 |
| Móc đơn staccato ngay sau nốt đen | cú thứ nhất của cặp | −2 |
| Móc đơn sau cú đó, không staccato | nốt lấy đà vào phách sau | −1 |
| Cả nửa ô là móc đơn, chỉ nốt đầu không staccato | nốt đầu 0, các móc staccato sau | −1 |

Bè trong chỉ đánh ở đầu nửa ô, đúng nốt không bị hạ. Lead không đụng.

`_contour_bourree_bass` không nhìn mỗi cặp `(duration 0.5, staccato)`. Cặp sau nốt đen hạ móc staccato 2 bậc và móc sau 1 bậc. Nửa ô toàn móc đơn giữ nốt đầu, rồi hạ các móc staccato sau 1 bậc. Nốt mở nửa ô phân biệt hai hình: nốt đen là cặp, móc đơn là nửa ô móc đơn.

Ô 0 của `test_bach_bourree_walks_under_a_hold_and_sits_under_a_running_treble` là câu phẳng `[72] * 8`. Bass `mf` là 60. Móc `1.0` thấp hơn nốt đen `0.0` đúng 4, móc `1.5` thấp hơn đúng 2. Nửa sau `2.0 / 3.0 / 3.5` lặp cùng hiệu.

Ô 1 của test đó là câu chạy, `rise` 7, trên `MIN_RISE`. `_under_lead` ở móc 0 ra bass 58, các móc sau ra 60. Trên ô đó nốt đen `1.0` không thấp hơn `0.0` đúng 2. Fixture lực của hình giá chạy là một câu có `rise < MIN_RISE`, để mọi móc cùng một mức lead. Câu lên thật giữ bậc nhờ extra cả ô ở mục 1.

### 5.2. Bach, Gavotte — nốt tốt và nốt xấu

`_render_bach_gavotte_bar`. Trong 4/4, nốt tốt là nốt rơi trên phách đen: móc 0, 4, 6. Nốt xấu là móc 5 và 7, và nốt đen staccato ở móc 2.

| Chỗ | Bậc | Bè nào hạ |
|---|---|---|
| Nốt đen móc 0 | 0 | — |
| Nốt đen staccato móc 2 | −1 | lead, bass, bè trong cùng một số |
| Móc đơn 4 và 6 | 0 | — |
| Móc đơn 5 và 7 | −1 | lead và bè song song |
| Bass dài từ móc 4 | 0 | Một nốt ngân cả bốn móc, không tách |

Hạ cả ba bè ở móc 2 để khoảng `lead > bass > bè trong` giữ nguyên. Ở bốn móc đơn, bass là một nốt. Hạ lead móc 5 và 7 chỉ khi mức mới còn cao hơn bass ít nhất 2. `mf` thì 64 xuống 62, bass là 60, còn đúng 2. `f` thì bass đã sát lead, bỏ bậc lead đó.

Test trên `_bach([72] * 16, character="calm")`, band mặc định `mf`. Lead: `1.0` thấp hơn `0.0` đúng 2. `2.5` và `3.5` thấp hơn `2.0` đúng 2. `3.0` bằng `2.0`. Bass `1.0` thấp hơn bass `0.0` đúng 2. Bass từ `2.0` không tách.

### 5.3. Bach, Sarabande — mordent và nốt passant

`_punch(..., amount=8)` chỉ cộng vào nốt có `_start16 == eighth * 2`, tức móc kép đầu của phách 2. Nốt láy và nốt trở về đang viết cùng lực với nốt chính, nên sau punch chỉ nốt chính nhô lên. Ba móc kép nghe như một cục.

Trong `_mordent_events`, trước punch:

| Móc kép | Bậc trên mức `_note_velocity` của phách 2 |
|---|---|
| Nốt chính, có accent | 0, rồi punch +8 |
| Nốt láy | −2 |
| Nốt trở về, nốt đen chấm | −1 |

Câu phẳng, mức viết 64: nghe `72, 60, 62`. Phách 2 vẫn là nhấn của sarabande.

Nhóm passant cuối ô đang là `_MELODY` đều. Giữ `_MELODY`. Mọi móc kép trừ móc cuối hạ 1. Móc cuối giữ `_MELODY`, vì nó dẫn sang phách sau. Cả nhóm vẫn dưới phách 2 đã punch. Không đổi độ dài, không đưa nhóm này sang `_note_velocity`.

### 5.4. Bach, Gigue — móc lấy đà

Nhấn đã có: downbeat accent và punch +6. Scale giữ nốt đầu `_MELODY_APEX`. Bè trong rải hợp âm giữ đều.

Chỉ lead ở `plan["pickup"]` mà không nằm trong `plan["down"]` hạ 1, trước punch. 6/8, đúng test `test_bach_gigue_breaks_the_chord_and_runs_when_the_line_rises`: phách `1.0` và `2.5` thấp hơn phách `0.0` đúng 2, trước khi tính thêm punch của `0.0` và `1.5`. Sau punch, downbeat còn cao hơn pickup 8 so với mức viết.

### 5.5. Bach, Prelude — móc kép trong phách

`_render_bach_prelude_bar`. Mỗi móc đơn là giá cộng một nốt bậc, hai móc kép cùng lực. Prelude vẫn là dòng đều. Một bậc Quantz trong cặp, không dâng cả ô.

Móc kép đúng phách giữ `_note_velocity`. Móc kép lệch phách hạ 1, sàn 40. Bass mỗi nửa ô giữ nguyên. `_softer_than_price` vẫn kéo bè trong xuống dưới nốt lead đang ngân. Bè trong étude-prelude thường quanh 46, dưới cả nốt đã hạ.

Test `test_bach_prelude_pairs_each_price_with_one_neighbor`: cùng cao độ như cũ, và `neighbor.velocity == strong.velocity - 2` khi cả hai còn trên sàn.

### 5.6. Bach, Allemande — bốn móc kép lấy đà

Thân style brisé giữ nguyên, kể cả bass bước khi lead ngân: bass bước đó hạ 1 sau `_shape_accompaniment`. Bè trong đang ngân trên móc đó, nếu chạm bass mới, hạ xuống `bass − 2`.

Bốn móc kép cuối ô, đang viết `_MELODY` đều, trở thành nốt lấy đà. Móc cuối bằng mức viết. Ba móc trước lần lượt `−3, −2, −1`. 4/4 là các phách `3.0, 3.25, 3.5, 3.75`. 3/4 và 6/8 là `2.0, 2.25, 2.5, 2.75`. Hướng dâng vào ô sau. Ngược với móng hạ trong một phách của Galop 1, vì đây là anacrusis của allemande.

`test_bach_allemande_weaves_style_brise_and_sixteenth_pickup` giữ chỗ và cấm staccato. Thêm hiệu lực `−6, −4, −2, 0` tính từ móc kép cuối.

### 5.7. Bach, Courante — tirata và hemiola

Tirata đang gán mọi móc kép bằng `_note_velocity` của móc đơn chứa nó, nên hai móc kép trong một phách bằng nhau. Hạ mọi móc kép của run đúng 1, trừ móc cuối, sau shape. Móc cuối là nốt tới, giữ mức viết. Không làm thang 2 từng nốt: run dài sẽ thành một chữ mới và nuốt nốt tới.

Ô đóng, `_courante_closes`, và meter là 3/4 hoặc 6/8. `hemiola()` đã gắn `accent` nhưng lực vẫn bằng nốt bên cạnh. 4/4 không có hemiola, hàm này đã trả false.

Giữ nốt hemiola ở mức viết. Bass courante là một nốt ngân cả ô, không tách theo móc. Ở `mf` câu phẳng, lead 64 cách bass 60 đúng 4. Hạ 2 bậc xuống 60 thì chạm bass. `_micro_fits` cho 1 bậc, lead yếu thành 62. Hạ sau `_shape_accompaniment` và `_softer_than_price`. `add_lead` chạy trước shape và chưa thấy bass, nên không tự trừ ở đó. Cờ `accent` của hemiola vẫn gắn trong `add_lead`.

| Meter | Giữ | Hạ 1 bậc |
|---|---|---|
| 3/4 | móc 0 và 3 | các móc đơn còn lại của ô đóng |
| 6/8 | móc 0, 2, 4 | móc 1, 3, 5 |
| 4/4 | cả ô | không hemiola |

Tirata vẫn hạ 1 bậc trừ nốt cuối, cũng sau shape, cùng `_micro_fits`. Cặp mở đầu cùng cao độ, nốt nhảy staccato ở móc 1, hạ 1 bậc cùng lúc. Nốt móc 0 giữ.

### 5.8. Bach, Chaconne — móc kép lệch trong phách

Bass nền và bè bariolage giữ. Scale breakout giữ nốt cuối `_MELODY_APEX`.

Trong mỗi nhóm bốn móc kép của giai điệu, móc lệch phách thấp hơn móc đúng phách của chính nhóm đó đúng 1. Lấy mức của móc đúng phách rồi trừ, để câu swell không bị móc lệch viết cứng `_MELODY` vượt lên.

Nhánh có bass ở đầu nhóm: móc `base` giữ `_note_velocity`, móc `base + 3` bằng mức đó trừ 2. Nhánh kia: móc `base` giữ `_MELODY`, móc `base + 2` bằng mức đó trừ 2.

### 5.9. Sor, Élégiaque — hành khúc

`_render_elegiaque_bar`, sau `_shape_accompaniment`. Lưới `_march_grid`. Ô sustain cuối câu, một bass ngân cả ô, bỏ contour.

| Nốt | Bậc |
|---|---|
| Nốt dài ở móc 0 | 0 |
| Nốt dài ở nửa sau: móc 4 của 4/4, móc 3 của 6/8, móc 4 của 3/4 | −1 |
| Nốt ngắn, một móc đơn (`duration_beats` 0.5) | −2 |

4/4, `mf`, câu phẳng: bass phách `0.0` là 60, phách `2.0` là 58, phách `1.5` và `3.5` là 56.

`thinner` của `mf` là `mp`. `_inner_eighths` đặt bè trong 56 tại móc 1, 3 và 6, tức phách `0.5`, `1.5`, `3.0`. Phách `1.5` là nốt ngắn và có bè trong cùng tiếng. Hạ bass 2 bậc xuống 56 thì chạm bè trong. Hạ bè trong ở đúng móc đó thêm 1 bậc, xuống 54, để nốt ngắn giữ −2 và còn cao hơn bè trong đúng 2. Phách `3.0` nằm trên nốt dài đã hạ 1, bass 58 vẫn cao hơn bè trong 56. Phách `3.5` không có bè trong.

### 5.10. Sor, biến tấu Op. 9 — nốt láy

`_render_mozart_var_bar`. Bè trong là một giai điệu bậc, giữ đều trên móc đơn. Chỉ móc kép nối, tức diminution, hạ 1 sau `_shape_accompaniment`.

Lúc dựng, ghi các beat của móc kép nối vào một set:

- `has_gap` và cầu hai nốt: cả hai `_spell16` trong khoảng trống.
- Không `has_gap`: `bridge[0]` ở nửa sau của móc trước, và `bridge[1]` nếu có. `tone` rơi trên móc kép thứ hai của móc đích là nốt cấu trúc, không vào set.

Móc đơn cấu trúc giữ mức `_shape_line`. Không dâng trong ô.

### 5.11. Barrios, Vals — bass giữa

`_render_vals_bar`. Cú sync ở phách `2.0` giữ `+4` và `accent`. Đó là chỗ 6/8 bắt chéo 3/4, và là cú snap của profile vals. Nốt lấy đà cuối ô giữ.

Bass gốc ở `0.0` là mốc. Bass quãng 5 ở `1.5`, không sync, hạ 1. Bè trong các móc `1, 2, 4, 5` giữ `_dance_velocity`. Phách 1 của vũ khúc còn nặng hơn bass giữa, cú Paraguay ở phách 2 vẫn là đỉnh của đệm.

### 5.12. Brouwer, Noviembre — nhịp đôi

`_render_noviembre_bar`. Hai xung bass, 4/4 ở `0.0` và `2.0`, đang cùng mức sau `_shape_accompaniment`. Nốt lấy đà cuối ô đã `_soften_attack` trừ 6. Test khóa `pulse ở 2.0 − pickup == 6`. Hạ xung `2.0` sẽ phá hiệu đó.

Vì vậy nâng xung đầu, `0.0`, đúng 1 bậc. Xung `2.0` và pickup đứng yên. Nâng chỉ khi bass mới còn dưới lead ít nhất 2 và không quá 64. Hết chỗ thì bỏ. `mf`, lead 64, bass 60: xung đầu thành 62, xung sau 60, pickup 54. `62` còn dưới lead đúng 2. Hiệu pickup giữ 6. Quầng bè trong giữ một mức.

6/8 dùng xung `0` và `3`. Cùng luật: xung đầu +1 bậc, xung sau và pickup giữ.

### 5.13. Brouwer, Étude — tumbao

`_render_etude_bar`, sau `_punch` +4 ở móc 0. Punch và `accent=True` chỉ ở cú đầu. Không thêm `accent` cho cú khác: snap của profile đang trỏ downbeat.

Ba trụ ngón cái trong 4/4 là móc `0`, `3`, `6` (phách `0.0`, `1.5`, `3.0`). Cú `6` là nốt chờ sang ô sau, `approach=True`. Cú giữa hạ 1 bậc. Cú chờ giữ mức sau shape. Cú đầu giữ punch.

| Meter | Giữ, đã punch | Hạ 1 bậc | Giữ, nốt chờ |
|---|---|---|---|
| 4/4 | móc 0 | móc 3 | móc 6 |
| 6/8 | móc 0 | móc 2 | móc 5 |
| 3/4 | móc 0 | móc 3 | không có nốt chờ |

Bè trong trên các móc trống giữ đều. Nếu bass giữa sau khi hạ không còn cao hơn bè trong đang ngân ít nhất 2, rút bậc về 0.

Ô `mf` 4/4, câu phẳng: bass `1.5` thấp hơn bass `3.0` đúng 2. Bass `0.0` vẫn cao hơn `3.0` vì punch +4. `test_brouwer_etude_plays_the_cuban_tumbao` giữ onset, độ dài, và `accent` ở cú đầu.

---

## 6. Chỗ gắn trong code

Hình lệch ở mục 1 nằm trong từng renderer. Helper dưới đây chỉ là cơ học. Galop giữ hàm riêng. Đợt này không đổ Galop qua helper mới.

```python
_MICRO = 2
_MICRO_FLOOR = 40

def _micro_drop(event: NoteEvent, steps: int) -> NoteEvent:
    """Lower one attack by `steps` micro degrees. The written level stays put at steps 0."""

def _micro_fits(lead: int, bass: int | None, support: int | None, steps: int) -> int:
    """Largest step count that keeps lead > bass > support by at least `_MICRO`."""

def _micro_raise(event: NoteEvent, steps: int, ceiling: int) -> NoteEvent:
    """Noviembre only. Raise the first pulse, and stop at `min(64, ceiling)`."""
```

`_micro_fits` nhận bậc muốn hạ và trả bậc còn chỗ. Hết chỗ thì trả 0. `_micro_raise` chỉ dùng cho xung đầu của Noviembre, vì xung sau đã bị khóa cách nốt lấy đà đúng 6.

| Hàm mới | Gọi ở cuối |
|---|---|
| `_contour_bourree_bass` | `_render_bach_bourree_bar`, sau shape, chỉ `low` |
| `_contour_gavotte` | `_render_bach_gavotte_bar`, sau shape |
| `_contour_allemande` | `_render_bach_allemande_bar`, sau shape, cho bass bước và cho bốn móc kép |
| `_contour_elegiaque_march` | `_render_elegiaque_bar`, sau shape, bỏ ô sustain |
| `_contour_mozart_diminution` | `_render_mozart_var_bar`, sau shape, trên set beat đã ghi |
| `_contour_vals_bass` | `_render_vals_bar`, trên nốt `beat == 1.5` không accent |
| `_contour_noviembre_pulse` | `_render_noviembre_bar`, sau `_soften_attack`, chỉ xung bass đầu |
| `_contour_tumbao` | `_render_etude_bar`, sau `_punch`, chỉ bass của tế bào giữa |
| `_contour_courante` | `_render_bach_courante_bar`, sau shape và `_softer_than_price` |

Sửa tại chỗ, vì nốt sinh ra đã là lead và punch diễn ra ngay sau:

| Chỗ | Sửa |
|---|---|
| `_mordent_events` | láy −2 bậc, trở về −1 bậc, trước `_punch` |
| passant sarabande | mọi `_spell16` trừ nốt cuối, −1 bậc trên `_MELODY` |
| gigue, nhánh `offset in plan["pickup"]` | `_note_velocity − _MICRO` trước punch |
| prelude, `_spell16` của neighbor | `velocity − _MICRO` |
| chaconne, móc kép lệch trong nhóm | mức móc đúng phách trừ `_MICRO` |

Không thêm cờ `NoteEvent`. Set beat của biến tấu là biến cục trong `_render_mozart_var_bar`.

---

## 7. Thứ tự làm

1. Helper và `_micro_fits`. Chưa gắn pattern. Test đơn vị: bậc 1 trên 64 ra 62, sàn 40 chặn, khoảng bass 2 thì bậc lead bị rút về 0. `_under_lead(64, "mf")` là bass 60, bè trong 56. Nhánh extra cả ô trong `_shape_dynamics` nhận thêm các pattern của mục 5.
2. Bourrée, Gavotte, Gigue. Ba điệu này chỉ là nhịp, dễ nghe lệch nếu gắn sai bè.
3. Mordent, passant, prelude, allemande, courante, chaconne.
4. Élégiaque và biến tấu Op. 9.
5. Vals, một nốt bass.
6. Noviembre và tumbao. Elogio và sarabande Brouwer không có bước này.

Mỗi bước một test hiệu trong ô, band `mf`, câu phẳng. Các test cao độ và onset đã có giữ nguyên. Noviembre giữ `pulse − pickup == 6`. Sau bước 6 chạy `backend/tests/test_sonify_guitar.py` và `backend/tests/test_bach_suite_doors.py`.

Không đụng `PROFILES` trong `guitar_wave.py`. Vi mô là vận tốc viết. Sóng vẫn cộng một tâm cho cả ô.
