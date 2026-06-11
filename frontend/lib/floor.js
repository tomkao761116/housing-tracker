/**
 * Unified floor parsing utility
 * Handles: '7', '九層', 'B2', '全', null, undefined
 * Returns: { display: string, raw: string|null }
 *   display: formatted string like "7F / 25F", "透天", "B2F / 10F"
 */

const NUM_MAP = {
  '零':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,
  '十':10,'十一':11,'十二':12,'十三':13,'十四':14,'十五':15,
  '十六':16,'十七':17,'十八':18,'十九':19,'二十':20,
};

export function parseFloor(val) {
  if (val == null || val === '' || val === '全') return null;
  
  const str = String(val).trim();
  
  // Already a plain number
  const num = parseInt(str, 10);
  if (!isNaN(num)) return num;
  
  // Chinese numeral (with or without 層 suffix)
  const cleaned = str.replace(/[層樓]/g, '');
  if (NUM_MAP[cleaned] !== undefined) return NUM_MAP[cleaned];
  
  return null;
}

export function formatFloor(floor, totalFloors) {
  const floorNum = parseFloor(floor);
  const totalNum = parseFloor(totalFloors);
  
  // 透天 / 整棟
  if (floor == null || floor === '全') {
    return '透天';
  }
  
  if (floorNum == null) {
    // Fallback: show raw value
    return typeof floor === 'string' && floor.includes('全') ? '透天' : String(floor);
  }
  
  const floorPart = floorNum < 0 ? `B${Math.abs(floorNum)}` : `${floorNum}`;
  const totalPart = totalNum != null ? `${totalNum}` : '?';
  
  return `${floorPart}F / ${totalPart}F`;
}
