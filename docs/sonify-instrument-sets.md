# Bộ nhạc cụ MuseSounds cho bốn kiểu nghe

Đề xuất hai bộ thêm cho mỗi variant. Năm vai trong bản nhạc giữ nguyên. Chỉ đổi nhạc cụ gắn vào từng vai. Mọi giọng dưới đây đều đang cài, `state = 1`, trong thư viện MuseSounds trên máy soạn.

Năm vai, đúng thứ tự part trong `musicxml.py`:

| Part | Vai |
|---|---|
| P5 | Điểm cao, thưa |
| P1 | Giai điệu |
| P2 | Bè giữa |
| P3 | Hợp âm hoặc lớp đệm |
| P4 | Bass |

## Ràng buộc của thư viện

Thư viện không có synth lead, synth pad, hay contrabass pizzicato. Jazz và Tối giản vẫn để bass là `Electric Bass`: bass đi bộ và nhịp bốn phách cần tiếng bật, trong khi `Contrabasses` và `Tuba` ngân bằng hơi hoặc vĩ.

Nốt dài của Ambient, và pad của Tối giản, chỉ giao cho hơi, dây hoặc giọng hát. Chuông, hộp nhạc và pad GM tắt ngay sau tiếng đánh, nên một nốt tròn trên giấy nghe thành nốt rời.

`_MUSE_VOICES` trong `backend/app/sonify/audio.py` hiện trỏ một phần các giọng này. Bộ mới cần thêm tên MusicXML và id nhạc cụ trước khi MuseScore gắn được đúng giọng.

## Giao hưởng

Bộ đang phát: Flute 1, Violins 1, Cellos, Piano, Electric Bass. Giai điệu violin nằm khoảng Sol3–Đô6. Flute điểm ở Sol5–Mi6. Bass vang ở C2–Si2.

Bộ gỗ hợp với những phiên ở `mp`. Bộ đồng hợp với những đoạn thanh khoản lên `mf`–`f`.

### Gỗ

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Piccolo | Piccolo |
| P1 | Oboe | Oboe |
| P2 | Clarinet in B♭ | Clarinet in Bb |
| P3 | Harp | Harp |
| P4 | Contrabassoon | Contrabassoon |

Oboe hát trong vùng violin. Nốt dưới Si♭3 gập lên một quãng tám. Clarinet thay cello. Harp đánh hợp âm hai khuông. Contrabassoon giữ bass ở C2–Si2, khác `Contrabasses` của Ambient.

### Đồng

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Glockenspiel | Glockenspiel |
| P1 | Trumpet | Trumpet |
| P2 | Trombone | Trombone |
| P3 | Sáu kèn cor | French Horns a6 |
| P4 | Tuba | Tuba |

Glockenspiel giữ vai điểm sáng ngắn của flute. Trumpet hát đến khoảng Si♭5; nốt cao hơn thì gập xuống. Trombone là bè giữa. Sáu kèn cor đệm hợp âm, khác kèn cor đơn đang làm tiếng nở ở Ambient. Tuba nằm ở C2–Si2.

## Jazz

Bộ đang phát: Vibraphone, Alto Sax, Tenor Sax, Suitcase Piano, Electric Bass. Cụm điểm cao nằm ở C6–F6. Giai điệu alto ở Sol3–La♭5, bè tenor ở C3–C4, hợp âm ở Fa2–Mi5.

### Soul

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Guitar điện LP | Electric LP - Clean |
| P1 | Trumpet | Trumpet |
| P2 | Trombone | Trombone |
| P3 | Wurly | Wurly 200A |
| P4 | Electric Bass | Electric Bass |

### Organ và sax

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Guitar điện SC | Electric SC - Clean |
| P1 | Soprano Sax | Soprano Saxophone |
| P2 | Baritone Sax | Baritone Saxophone |
| P3 | Hammond | Hammond Organ |
| P4 | Electric Bass | Electric Bass |

Guitar chỉ đánh cụm ngắn ở C6–F6. LP và SC là hai giọng khác nhau trong Muse Guitars Vol. 1. Trumpet chạm trần ở La♭5. Soprano gập lên từ Si♭3. Baritone nằm ở C3–C4. Wurly và Hammond đánh được hợp âm Fa2–Mi5.

## Tối giản

Bộ đang phát là synth GM, qua MS Basic: Synth Bell, Synth Arpeggio, Synth Pad, Synth Pulse, Sub-Bass. Arpeggio chạy Đô3–Đô6. Pad giữ hai nốt Si♭2–Sol♯4 suốt ô nhịp. Pulse cần cả cú chặn ở Đô2 và dải Đô5–Mi6. Chuông là một nốt Đô6–Sol6.

### Mallet

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Crotales | Crotales |
| P1 | Marimba | Marimba |
| P2 | Hợp xướng | Full Choir |
| P3 | Harpsichord | Harpsichord |
| P4 | Electric Bass | Electric Bass |

### Guitar và dây

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Flute 2 | Flute 2 |
| P1 | Guitar thép | Acoustic Steel Plucked |
| P2 | Cello | Cellos |
| P3 | Piano đứng | Upright Piano |
| P4 | Electric Bass | Electric Bass |

Marimba và guitar thép gánh ostinato. Harpsichord và piano đứng gánh pulse vì phải xuống tới Đô2. Full Choir và Cellos giữ pad suốt ô nhịp. Crotales và Flute 2 chỉ điểm ở Đô6–Sol6.

## Ambient

Bộ đang phát: Celesta, Alto Flute, Bass Flute, French Horn, Contrabasses. Kính ngân ở Sol3–Đô6 và lắng bằng diminuendo. Halo là hai nốt Rê3–Đô♯4. Tiếng nở là hợp âm Đô3–La4. Drone ở C2. Shimmer là một nốt tròn Rê5–Đô6.

### Hơi trầm

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Handchimes | Handchimes |
| P1 | Cor anglais | English Horn |
| P2 | Bass clarinet | Bass Clarinet |
| P3 | Ba trombone | Trombones a3 |
| P4 | Contrabassoon | Contrabassoon |

### Hợp xướng

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Handbells | Handbells |
| P1 | Clarinet | Clarinet in Bb |
| P2 | Giọng tenor | Tenors |
| P3 | Viola | Violas |
| P4 | Giọng bass | Basses |

Handchimes và Handbells ngân hết nốt tròn, khác Celesta. Cor anglais và clarinet phủ Sol3–Đô6, nên hơi kính vẫn diminuendo trên cùng một tiếng. Bass clarinet và tenor giữ halo. Trombones a3 và viola nở hợp âm. Contrabassoon và Basses giữ drone ở C2.

## Giọng xuất hiện ở hơn một kiểu

Cùng một giọng MuseSounds có thể đứng ở hai kiểu vì bài không phát chồng. Vai viết thì khác:

| Giọng | Chỗ dùng |
|---|---|
| Trumpet, Trombone | Giai điệu và bè giữa của Jazz Soul; giai điệu và bè giữa của Giao hưởng Đồng |
| Contrabassoon | Bass của Giao hưởng Gỗ; drone của Ambient Hơi trầm |
| Clarinet in Bb | Bè giữa của Giao hưởng Gỗ; kính của Ambient Hợp xướng |
| Cellos | Bè giữa của Giao hưởng hiện tại; pad của Tối giản Guitar và dây |
| Electric Bass | Bass của Giao hưởng hiện tại, của cả hai bộ Jazz, và của cả hai bộ Tối giản |
