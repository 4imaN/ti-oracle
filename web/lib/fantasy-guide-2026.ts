import type { RecognizedBanner } from "@/lib/types";

export type GuideRole = "Core" | "Mid" | "Support";
export type EmblemColor = "Red" | "Green" | "Blue";

export type GuidePair = {
  role: GuideRole;
  players: string[];
  average: number;
  top: number;
  stats: Record<string, number>;
};

export const GUIDE_SOURCE = {
  name: "Maroomm · Fantasy League 2026 Guide",
  url: "https://www.reddit.com/r/DotA2/comments/1vble84/fantasy_league_2026_guide/",
  published: "2026-07-31",
  sample: "13 Tier-1 tournaments · 1,601 maps",
};

export const STAGE_PATTERNS: Record<GuideRole, Record<"Group Stage" | "The International", EmblemColor[]>> = {
  Core: { "Group Stage": ["Red", "Green", "Red"], "The International": ["Red", "Green", "Red", "Green", "Red"] },
  Mid: { "Group Stage": ["Red", "Blue", "Green"], "The International": ["Red", "Blue", "Green", "Red", "Green"] },
  Support: { "Group Stage": ["Blue", "Green", "Blue"], "The International": ["Blue", "Green", "Blue", "Green", "Blue"] },
};

export const METRIC_PRIORITIES: Record<GuideRole, Partial<Record<EmblemColor, string[]>>> = {
  Core: {
    Red: ["Creeps", "GPM", "Deaths", "Towers", "Kills", "Madstones"],
    Green: ["Teamfight", "Roshan", "Tormentor", "Stuns", "Courier kills", "First blood"],
  },
  Mid: {
    Red: ["Creeps", "GPM", "Deaths", "Kills", "Madstones", "Towers"],
    Green: ["Teamfight", "Stuns", "Tormentor", "Roshan", "Courier kills", "First blood"],
    Blue: ["Runes", "Camps stacked", "Lotuses", "Wards", "Smokes", "Watchers"],
  },
  Support: {
    Blue: ["Wards", "Smokes", "Lotuses", "Camps stacked", "Watchers", "Runes"],
    Green: ["Teamfight", "Tormentor", "Courier kills", "Stuns", "First blood", "Roshan"],
  },
};

export const TRAIT_PRIORITY = ["Friendly", "Vampiric", "Benevolent", "Unique", "Fractal"] as const;

const coreRows: Array<[string, number, number, number[]]> = [
  ["YSR-04E & niu", 1620, 2751, [2539,2925,2334,1247,1585,1624,2941,554,1893,1082,447,270]],
  ["Satanic & Noticed",1570,4130,[2723,2677,2539,1293,1609,1696,2608,607,1222,1117,487,263]],
  ["Yuma & Wisper",1560,4534,[2644,2359,2753,1403,1639,1017,2728,642,1372,1261,427,481]],
  ["watson & DM",1559,4206,[2668,2643,2563,1374,1478,1256,2654,597,1447,1126,504,395]],
  ["Kiritych & MieRo",1540,4437,[2574,2501,2548,1317,1350,1555,2627,530,1534,1281,432,236]],
  ["skiter & ATF",1519,4573,[2637,2275,2638,958,1586,1488,2544,596,1507,1114,312,572]],
  ["Ame & Xxs",1513,4299,[2550,2436,2744,1371,1236,1448,2595,597,1482,962,392,343]],
  ["Nightfall & Ws",1490,4298,[2586,2606,2289,1197,1568,1238,2645,655,1363,1075,355,307]],
  ["Pure & 33",1483,4586,[2680,2227,2648,1250,1476,1241,2620,484,1378,1004,323,464]],
  ["Yatoro & Collapse",1475,4153,[2593,2216,2471,1175,1462,1387,2596,610,1356,991,450,388]],
  ["shiro & Bach",1464,3838,[2461,2407,2549,1252,1177,1309,2599,674,1512,1101,354,171]],
  ["Ghost & Fayde",1419,4002,[2492,2161,2438,1226,1343,1310,2593,616,1114,897,542,296]],
  ["miCKe & Ace",1415,4518,[2475,2287,2423,953,1390,1319,2606,688,1433,829,300,272]],
  ["ssnovv1 & Corrupted",1354,3686,[2487,2240,2337,1103,1093,1354,2595,688,1103,729,232,285]],
  ["Natsumi & Raven",1351,2942,[2449,2541,2471,1138,1128,1098,2793,385,843,666,389,309]],
  ["SumaiL & Davai",1249,3419,[2329,2020,2057,892,1407,708,2742,803,859,379,333,462]],
];

const midRows: Array<[string, number, number, number[]]> = [
  ["Nisha",798,2524,[1267,1262,1212,521,894,478,1483,316,500,324,107,377]],
  ["Marl1ne",781,2333,[1215,1122,1161,532,837,383,1500,494,677,330,215,193]],
  ["gpk",771,2148,[1228,1273,1213,536,831,345,1487,352,579,422,132,157]],
  ["lorenof",757,2057,[1273,1378,1095,405,849,525,1450,279,324,384,127,340]],
  ["Echozz",745,1214,[1104,1425,962,616,520,217,1549,278,541,270,149,324]],
  ["Mikoto",740,1916,[1239,1414,1170,491,852,374,1446,257,302,238,106,170]],
  ["bzm",738,2192,[1265,1045,1203,255,786,439,1481,451,538,313,70,285]],
  ["No[o]ne",737,1941,[1220,1324,1079,442,768,405,1496,312,471,297,186,174]],
  ["Xm",728,1982,[1211,1184,1244,570,728,258,1519,311,482,172,118,257]],
  ["TaiLung",725,2137,[1230,1133,1285,484,690,499,1395,292,424,437,105,102]],
  ["Larl",715,1902,[1220,1147,1182,527,847,277,1480,333,447,209,49,125]],
  ["CHIRA_JUNIOR",712,2047,[1193,1227,1034,369,763,429,1429,393,474,258,151,239]],
  ["RCY",710,2013,[1236,1270,1170,407,867,362,1488,295,367,250,75,218]],
  ["NothingToSay",694,2062,[1154,1178,1159,462,673,176,1539,363,473,188,74,144]],
  ["Mirage`",676,1767,[1159,1112,1001,397,767,194,1517,344,220,195,161,281]],
  ["Yopaj",664,1751,[1080,1224,967,453,734,281,1557,324,312,208,147,62]],
];

const supportRows: Array<[string, number, number, number[]]> = [
  ["Thiolicor & KJ",1505,5047,[2260,2349,1755,2418,1403,2016,2719,852,760,149,334,1042]],
  ["Saksa & Malady",1328,4327,[2012,2038,1365,1850,1013,1704,2859,766,904,116,507,808]],
  ["TIMS & skem",1313,3807,[1962,2334,1468,1961,832,1966,2836,703,678,134,294,587]],
  ["Cr1t- & Sneyking",1312,4276,[2166,1914,1350,1779,957,1904,2686,749,1066,195,335,647]],
  ["fy & xNova",1305,4130,[2202,1896,1212,1940,844,2013,2863,756,800,106,496,532]],
  ["Ari & Whitemon",1274,4107,[2133,1869,1176,1915,740,1728,2818,904,868,64,574,495]],
  ["Mira & kaori",1252,4059,[2002,1589,1190,1706,793,1858,2763,951,932,104,484,655]],
  ["OmaR & GH",1251,3579,[1989,1508,1359,1851,695,1896,2754,831,971,122,504,532]],
  ["Boxi & tOfu",1249,4243,[2069,1766,1163,1618,631,1843,2900,726,1128,96,458,591]],
  ["rue & not me",1240,3925,[2174,1895,1515,1382,659,1729,2881,1018,697,70,400,458]],
  ["XinQ & y`",1232,3632,[2134,1465,1109,2316,853,1813,2922,675,693,51,288,459]],
  ["9Class & Dukalis",1165,3847,[2039,1611,1224,1228,768,1841,2777,637,831,91,396,537]],
  ["planet & zzq",1163,2334,[1881,1841,987,1293,690,1887,2981,547,1010,73,60,701]],
  ["Save- & Kataomi",1160,3803,[2190,1240,909,1317,729,1965,2840,862,863,124,504,380]],
  ["Bignum & Speeed",1144,3713,[1904,1681,870,1129,758,2014,2809,790,751,91,432,505]],
  ["sayuw & RESPECT",1108,3186,[1894,1449,1034,1255,730,1839,2866,690,472,18,569,477]],
];

const redGreenMetrics = ["GPM","Deaths","Creeps","Madstones","Kills","Towers","Teamfight","Stuns","Tormentor","Roshan","First blood","Courier kills"];
const blueGreenMetrics = ["Wards","Camps stacked","Lotuses","Watchers","Runes","Smokes","Teamfight","Stuns","Tormentor","Roshan","First blood","Courier kills"];

function rowsToPairs(role: GuideRole, rows: Array<[string, number, number, number[]]>, metrics: string[]): GuidePair[] {
  return rows.map(([names, average, top, values]) => ({
    role,
    players: names.split(" & "),
    average,
    top,
    stats: Object.fromEntries(metrics.map((metric, index) => [metric, values[index]])),
  }));
}

export const GUIDE_PAIRS: GuidePair[] = [
  ...rowsToPairs("Core", coreRows, redGreenMetrics),
  ...rowsToPairs("Mid", midRows, redGreenMetrics),
  ...rowsToPairs("Support", supportRows, blueGreenMetrics),
];

const prefixRows = [
  "YSR-04E|Otherworldly:31,Emerald:23,Golden:23,Heroic:23,Cerulean:15,Royal:8",
  "niu|Golden:38,Elemental:38,Crimson:31,Emerald:31,Royal:23,Otherworldly:23,Heroic:23",
  "Satanic|Otherworldly:24,Heroic:24,Emerald:19,Royal:16,Golden:15,Cerulean:14,Crimson:12,Elemental:10",
  "Noticed|Elemental:39,Crimson:37,Golden:25,Emerald:23,Royal:22,Otherworldly:15,Heroic:4,Cerulean:3",
  "Yuma|Otherworldly:26,Golden:25,Royal:23,Emerald:22,Heroic:22,Cerulean:12,Crimson:11,Elemental:11",
  "Wisper|Crimson:44,Elemental:31,Golden:30,Royal:23,Emerald:21,Otherworldly:15,Heroic:14,Cerulean:4",
  "watson|Royal:28,Otherworldly:21,Crimson:17,Heroic:17,Golden:14,Emerald:13,Cerulean:12,Elemental:12",
  "DM|Golden:43,Crimson:37,Elemental:33,Otherworldly:20,Royal:15,Emerald:14,Cerulean:8,Heroic:5",
  "Kiritych|Heroic:35,Otherworldly:24,Emerald:23,Royal:21,Golden:20,Cerulean:16,Elemental:10,Crimson:6",
  "MieRo|Golden:34,Crimson:31,Emerald:30,Elemental:26,Royal:14,Otherworldly:14,Heroic:7,Cerulean:6",
  "skiter|Golden:35,Heroic:25,Otherworldly:21,Crimson:14,Elemental:14,Emerald:13,Royal:13,Cerulean:7",
  "ATF|Crimson:34,Elemental:25,Emerald:24,Otherworldly:20,Golden:17,Royal:16,Cerulean:9,Heroic:2",
  "Ame|Royal:24,Otherworldly:24,Golden:21,Heroic:19,Elemental:17,Crimson:15,Emerald:12,Cerulean:10",
  "Xxs|Crimson:44,Elemental:35,Golden:33,Royal:21,Emerald:13,Otherworldly:10,Heroic:5,Cerulean:3",
  "Nightfall|Heroic:36,Royal:25,Emerald:24,Golden:19,Otherworldly:14,Crimson:14,Cerulean:11,Elemental:8",
  "Ws|Crimson:41,Golden:37,Emerald:24,Elemental:24,Royal:18,Otherworldly:10,Cerulean:1",
  "Pure|Heroic:36,Otherworldly:33,Emerald:22,Crimson:19,Cerulean:18,Royal:18,Elemental:16,Golden:13",
  "33|Elemental:43,Crimson:40,Golden:36,Emerald:30,Otherworldly:18,Royal:15,Heroic:9,Cerulean:1",
  "Yatoro|Royal:24,Heroic:24,Golden:21,Otherworldly:21,Elemental:17,Crimson:15,Emerald:14,Cerulean:11",
  "Collapse|Crimson:50,Golden:35,Elemental:32,Emerald:24,Otherworldly:15,Royal:12,Heroic:9,Cerulean:1",
  "shiro|Heroic:40,Emerald:28,Otherworldly:24,Golden:23,Royal:20,Crimson:11,Elemental:9,Cerulean:7",
  "Bach|Crimson:49,Golden:33,Elemental:21,Emerald:17,Otherworldly:17,Royal:16,Heroic:7,Cerulean:4",
  "Ghost|Otherworldly:42,Emerald:31,Heroic:28,Golden:23,Crimson:18,Cerulean:18,Royal:18,Elemental:18",
  "Fayde|Golden:29,Elemental:27,Crimson:24,Royal:24,Emerald:22,Otherworldly:18,Cerulean:17,Heroic:2",
  "miCKe|Heroic:38,Emerald:29,Otherworldly:22,Golden:20,Crimson:18,Cerulean:13,Elemental:12,Royal:8",
  "Ace|Crimson:37,Golden:34,Elemental:34,Emerald:27,Otherworldly:19,Royal:8,Heroic:8,Cerulean:5",
  "ssnovv1|Otherworldly:31,Heroic:31,Cerulean:21,Royal:21,Emerald:20,Golden:11,Crimson:9,Elemental:5",
  "Corrupted|Emerald:36,Elemental:35,Golden:31,Crimson:29,Otherworldly:21,Royal:13,Heroic:5,Cerulean:3",
  "Natsumi|Otherworldly:30,Heroic:28,Golden:22,Elemental:19,Emerald:18,Royal:18,Cerulean:16,Crimson:13",
  "Raven|Crimson:50,Emerald:30,Otherworldly:30,Golden:20,Elemental:20,Royal:10",
  "SumaiL|Otherworldly:56,Elemental:27,Crimson:25,Royal:20,Golden:19,Cerulean:17,Emerald:12,Heroic:12",
  "Davai|Emerald:37,Crimson:32,Elemental:32,Golden:24,Otherworldly:22,Royal:14,Heroic:2",
  "Nisha|Otherworldly:53,Cerulean:31,Elemental:29,Crimson:28,Royal:16,Heroic:9,Golden:6,Emerald:6",
  "Malr1ne|Crimson:50,Golden:34,Otherworldly:21,Elemental:20,Heroic:12,Emerald:10,Cerulean:9,Royal:7",
  "gpk|Otherworldly:45,Crimson:34,Elemental:32,Cerulean:27,Royal:16,Emerald:7,Heroic:6,Golden:2",
  "lorenof|Otherworldly:55,Crimson:36,Cerulean:34,Elemental:29,Emerald:19,Heroic:5,Royal:2,Golden:1",
  "Echozz|Crimson:38,Otherworldly:31,Elemental:23,Cerulean:15,Royal:15,Golden:15",
  "Mikoto|Otherworldly:52,Cerulean:40,Crimson:25,Elemental:17,Heroic:12,Emerald:11,Royal:9",
  "bzm|Otherworldly:38,Crimson:32,Elemental:29,Heroic:19,Golden:19,Cerulean:15,Royal:12,Emerald:4",
  "No[o]ne|Otherworldly:37,Crimson:37,Elemental:27,Cerulean:21,Heroic:14,Royal:10,Golden:8,Emerald:8",
  "Xm|Otherworldly:44,Cerulean:34,Crimson:28,Elemental:20,Emerald:12,Golden:9,Royal:6,Heroic:6",
  "TaiLung|Crimson:26,Cerulean:25,Otherworldly:25,Emerald:19,Golden:18,Elemental:16,Royal:7,Heroic:5",
  "Larl|Otherworldly:36,Cerulean:28,Crimson:27,Elemental:21,Heroic:14,Golden:13,Royal:9,Emerald:6",
  "CHIRA_JUNIOR|Elemental:40,Otherworldly:33,Royal:23,Heroic:21,Cerulean:20,Crimson:16,Emerald:12,Golden:6",
  "RCY|Otherworldly:51,Cerulean:25,Crimson:24,Elemental:21,Emerald:12,Heroic:10,Golden:7,Royal:5",
  "NothingToSay|Otherworldly:33,Crimson:31,Cerulean:31,Golden:28,Elemental:11,Heroic:10,Emerald:4,Royal:4",
  "Mirage|Otherworldly:53,Elemental:40,Crimson:37,Cerulean:20,Royal:12,Emerald:8,Golden:8,Heroic:7",
  "Yopaj|Otherworldly:39,Crimson:29,Cerulean:28,Elemental:15,Royal:13,Golden:13,Emerald:10,Heroic:6",
  "Thiolicor|Heroic:41,Emerald:35,Golden:26,Elemental:24,Crimson:18,Otherworldly:15,Cerulean:14,Royal:5",
  "KJ|Heroic:34,Crimson:30,Golden:26,Emerald:24,Elemental:21,Cerulean:17,Royal:17,Otherworldly:8",
  "Saksa|Heroic:48,Golden:44,Emerald:30,Crimson:17,Otherworldly:16,Elemental:12,Cerulean:5,Royal:3",
  "Malady|Crimson:44,Elemental:43,Cerulean:31,Golden:26,Heroic:21,Emerald:16,Royal:9,Otherworldly:9",
  "TIMS|Heroic:43,Emerald:25,Golden:25,Crimson:23,Royal:15,Otherworldly:15,Elemental:13,Cerulean:9",
  "skem|Golden:32,Crimson:25,Elemental:23,Cerulean:16,Heroic:16,Royal:14,Emerald:13,Otherworldly:4",
  "Cr1t-|Heroic:59,Emerald:39,Golden:33,Otherworldly:29,Crimson:28,Royal:12,Cerulean:7,Elemental:5",
  "Sneyking|Golden:42,Elemental:42,Crimson:33,Cerulean:25,Heroic:18,Emerald:16,Otherworldly:16,Royal:9",
  "fy|Heroic:41,Emerald:40,Golden:39,Elemental:17,Otherworldly:16,Crimson:15,Royal:11,Cerulean:6",
  "xNova|Crimson:45,Elemental:43,Golden:37,Cerulean:22,Heroic:16,Emerald:15,Otherworldly:10,Royal:10",
  "Ari|Golden:49,Heroic:48,Emerald:29,Elemental:11,Royal:10,Otherworldly:9,Crimson:8,Cerulean:1",
  "Whitemon|Elemental:52,Crimson:44,Golden:41,Cerulean:21,Heroic:15,Royal:13,Otherworldly:12,Emerald:11",
  "Mira|Heroic:43,Emerald:40,Royal:29,Otherworldly:24,Golden:23,Crimson:12,Elemental:7,Cerulean:1",
  "kaori|Crimson:76,Elemental:53,Heroic:33,Golden:29,Cerulean:27,Emerald:13,Otherworldly:9,Royal:4",
  "OmaR|Emerald:42,Heroic:42,Golden:38,Crimson:14,Elemental:13,Cerulean:4,Royal:3,Otherworldly:1",
  "GH|Elemental:37,Golden:37,Cerulean:27,Crimson:25,Royal:23,Heroic:7,Emerald:6,Otherworldly:3",
  "Boxi|Heroic:32,Golden:29,Emerald:29,Elemental:26,Crimson:18,Otherworldly:17,Royal:5,Cerulean:5",
  "tOfu|Crimson:38,Heroic:35,Golden:29,Elemental:27,Emerald:22,Cerulean:20,Royal:12,Otherworldly:11",
  "rue|Golden:36,Heroic:35,Emerald:34,Elemental:20,Otherworldly:19,Royal:14,Crimson:13,Cerulean:8",
  "not me|Heroic:50,Emerald:43,Golden:37,Crimson:24,Elemental:23,Otherworldly:11,Royal:9,Cerulean:5",
  "XinQ|Heroic:52,Emerald:48,Golden:37,Cerulean:16,Crimson:13,Otherworldly:11,Elemental:8,Royal:5",
  "y`|Elemental:45,Crimson:34,Cerulean:34,Emerald:27,Golden:22,Otherworldly:17,Heroic:15,Royal:10",
  "9Class|Golden:45,Heroic:37,Emerald:36,Otherworldly:13,Cerulean:10,Royal:10,Elemental:8,Crimson:7",
  "Dukalis|Elemental:37,Crimson:35,Golden:30,Cerulean:24,Heroic:17,Emerald:14,Otherworldly:11,Royal:10",
  "planet|Emerald:47,Golden:38,Heroic:31,Royal:22,Otherworldly:16,Crimson:9,Cerulean:9,Elemental:9",
  "zzq|Elemental:54,Cerulean:46,Crimson:23,Royal:23,Golden:23,Emerald:8,Heroic:8",
  "Save-|Heroic:51,Emerald:42,Golden:42,Otherworldly:20,Crimson:15,Royal:12,Cerulean:6,Elemental:6",
  "Kataomi|Elemental:50,Cerulean:38,Crimson:32,Royal:17,Heroic:17,Golden:11,Emerald:10,Otherworldly:9",
  "Bignum|Emerald:40,Heroic:35,Golden:31,Elemental:21,Crimson:20,Royal:20,Otherworldly:15,Cerulean:6",
  "Speeed|Crimson:49,Elemental:42,Golden:38,Heroic:33,Emerald:21,Cerulean:15,Otherworldly:9,Royal:5",
  "sayuw|Emerald:62,Heroic:40,Golden:34,Crimson:16,Otherworldly:14,Elemental:12,Royal:10,Cerulean:4",
  "RESPECT|Golden:46,Emerald:34,Crimson:32,Elemental:32,Heroic:20,Otherworldly:12,Royal:11,Cerulean:8",
];

function compactName(value: string): string {
  const compact = value.toLowerCase().replace(/[^a-z0-9]+/g, "");
  return ({ kingjungles: "kj", marl1ne: "malr1ne" } as Record<string, string>)[compact] ?? compact;
}

export const PREFIX_RATES: Record<string, Record<string, number>> = Object.fromEntries(prefixRows.map((row) => {
  const [player, rates] = row.split("|");
  return [compactName(player), Object.fromEntries(rates.split(",").map((entry) => {
    const [prefix, percentage] = entry.split(":");
    return [prefix, Number(percentage)];
  }))];
}));

export function guidePrefixRate(player: string | null, prefix: string | null): number {
  if (!player || !prefix) return 0;
  const key = compactName(player);
  return PREFIX_RATES[key]?.[prefix] ?? 0;
}

export function guideMetricRank(role: GuideRole, color: EmblemColor, metric: string): number {
  const priorities = METRIC_PRIORITIES[role][color] ?? [];
  const index = priorities.indexOf(metric);
  return index < 0 ? 0.2 : 1 - index / Math.max(priorities.length, 1) * 0.72;
}

export function expectedEmblemCount(banners: RecognizedBanner[]): 3 | 5 {
  return banners.some((banner) => banner.slot > 3) ? 5 : 3;
}
