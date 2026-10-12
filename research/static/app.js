// Lọc bảng mã ở trang Hôm nay theo nhóm trạng thái, ô tìm mã và ngành. Không gọi server.
(function () {
  const table = document.querySelector("table.verdicts");
  if (!table) return;
  const rows = Array.from(table.tBodies[0].rows);
  const tabs = Array.from(document.querySelectorAll(".tabs .tab"));
  const search = document.getElementById("tim-ma");
  const industry = document.getElementById("loc-nganh");
  const empty = document.getElementById("khong-co-ma");
  let lane = "";

  function apply() {
    const text = (search && search.value.trim().toUpperCase()) || "";
    const group = (industry && industry.value) || "";
    let shown = 0;
    for (const row of rows) {
      const visible =
        (!lane || row.dataset.lane === lane) &&
        (!text || row.dataset.symbol.includes(text)) &&
        (!group || row.dataset.industry === group);
      row.hidden = !visible;
      if (visible) shown += 1;
    }
    if (empty) empty.hidden = shown > 0;
  }

  for (const tab of tabs) {
    tab.addEventListener("click", () => {
      lane = tab.dataset.lane;
      for (const other of tabs) other.classList.toggle("active", other === tab);
      apply();
    });
  }
  if (search) search.addEventListener("input", apply);
  if (industry) industry.addEventListener("change", apply);
})();
