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
  '二十一':21,'二十二':22,'二十三':23,'二十四':24,'二十五':25,
  '二十六':26,'二十七':27,'二十八':28,'二十九':29,'三十':30,
  '三十一':31,'三十二':32,'三十三':33,'三十四':34,'三十五':35,
  '三十六':36,'三十七':37,'三十八':38,'三十九':39,'四十':40,
  '四十一':41,'四十二':42,'四十三':43,'四十四':44,'四十五':45,
  '四十六':46,'四十七':47,'四十八':48,'四十九':49,'五十':50,
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
  
  // Dynamic parsing for numbers > 50: "六十", "六十三", etc.
  // Pattern: [十位數字]十[個位數字]?
  const tenMatch = cleaned.match(/^([二三四五六七八九十])十([一二三四五六七八九])?$/);
  if (tenMatch) {
    const tens = NUM_MAP[tenMatch[1]];
    const ones = tenMatch[2] ? NUM_MAP[tenMatch[2]] : 0;
    if (tens != null) return tens * 10 + ones;
  }

  // Handle multiple floors separated by comma/ideographic comma: "十層，十一層"
  // Take the first one for display
  const multiPart = cleaned.split(/[,，、]/);
  if (multiPart.length > 1) {
    const firstParsed = parseFloor(multiPart[0].replace(/[層樓]/g, ''));
    if (firstParsed != null) return firstParsed;
  }
  
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
