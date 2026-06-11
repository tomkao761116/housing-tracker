// 樓層格式化共用函數

function parseFloorNum(val) {
  if (val == null) return null;
  if (typeof val === 'number') return val;
  const match = String(val).match(/(\d+)/);
  return match ? parseInt(match[1], 10) : null;
}

const CHINESE_DIGITS = {
  '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
  '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
  '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
  '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20,
  '二十一': 21, '二十二': 22, '二十三': 23, '二十四': 24, '二十五': 25,
  '二十六': 26, '二十七': 27, '二十八': 28, '二十九': 29, '三十': 30
};

function parseChineseFloor(str) {
  if (str == null) return null;
  const s = String(str).replace('層', '').trim();
  return CHINESE_DIGITS[s] || null;
}

export function formatFloor(floor, totalFloors, buildingType) {
  if (floor == null) return '';

  const floorStr = String(floor).trim();
  const totalStr = String(totalFloors ?? '').trim();

  // 判斷是否為整棟（floor 包含「全」）
  const isEntireBuilding = floorStr.includes('全');

  // 透天厝／別墅 或 整棟：顯示「共N層」
  if ((buildingType?.includes('透天') || buildingType?.includes('別墅') || isEntireBuilding) && totalStr) {
    const num = parseFloorNum(totalStr) ?? parseChineseFloor(totalStr);
    return num != null ? `共${num}層` : totalStr;
  }

  // 一般：顯示「XF / YF」
  const floorNum = parseFloorNum(floorStr) ?? parseChineseFloor(floorStr);
  const totalNum = parseFloorNum(totalStr) ?? parseChineseFloor(totalStr);

  if (totalNum != null && floorNum != null) return `${floorNum}F / ${totalNum}F`;
  if (floorNum != null) return `${floorNum}F`;
  return floorStr;
}
