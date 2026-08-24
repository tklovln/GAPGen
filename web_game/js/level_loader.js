// level_loader.js — 移植 json_level_loader.gd + obstacle.gd
import { K } from './util.js';
import { ELEMENT_TO_COLOR_INDEX } from './tiles.js';

const OBSTACLE_TYPE_MAP = {
  Crt: 'jelly', Puddle: 'jelly', Rope: 'wire', Mud: 'wire',
  TrafficCone: 'jelly', SalmonCan: 'jelly', Barrel: 'jelly',
  Stamp: 'manufacturer', WaterChiller: 'jelly', BeverageChiller: 'jelly',
  Pool: 'jelly', Roadblock: 'jelly',
};

const BLOCKING_OBSTACLE_PREFIXES = [
  'Crt', 'Barrel', 'TrafficCone', 'SalmonCan', 'Stamp',
  'WaterChiller', 'BeverageChiller', 'Pool', 'Roadblock',
];

const POWERUP_TYPE_MAP = {
  Soda0d: 'striped_h', Soda90: 'striped_v', TNT: 'wrapped',
  TrPr: 'spiral', LtBl: 'color_bomb',
};

const isBlockingObstacle = (tid) => BLOCKING_OBSTACLE_PREFIXES.some((p) => tid.startsWith(p));
const resolveObstacleType = (tid) => {
  for (const prefix of Object.keys(OBSTACLE_TYPE_MAP)) {
    if (tid.startsWith(prefix)) return OBSTACLE_TYPE_MAP[prefix];
  }
  return null;
};

function resolveObstacleHp(tileId) {
  const lvIdx = tileId.indexOf('_lv');
  if (lvIdx >= 0) {
    const n = parseInt(tileId.substring(lvIdx + 3), 10);
    if (n > 0) return n;
  }
  if (tileId.startsWith('WaterChiller')) return 11;
  if (tileId.startsWith('BeverageChiller')) return 5;
  if (tileId.startsWith('SalmonCan')) return 2;
  if (tileId === 'Pool' || tileId === 'Pool_lv1') return 5;
  const last = tileId[tileId.length - 1];
  if (last >= '1' && last <= '9') return parseInt(last, 10);
  return 1;
}

function parseLevelIdFromName(nameStr) {
  if (!nameStr) return 1;
  const m = nameStr.toLowerCase().match(/(\d+)\s*$/) || nameStr.match(/_(\d+)/);
  return m ? parseInt(m[1], 10) : 1;
}

const goalFamily = (tid) => {
  for (const prefix of ['WaterChiller', 'BeverageChiller', 'TrafficCone', 'SalmonCan', 'Roadblock', 'Puddle', 'Crt', 'Barrel', 'Pool', 'Stamp', 'Rope', 'Mud']) {
    if (tid.startsWith(prefix)) return prefix;
  }
  return '';
};

export function parseLevelDict(data) {
  const level = {
    levelId: parseLevelIdFromName(String(data.name || '')),
    gridWidth: Number(data.cols ?? 9),
    gridHeight: Number(data.rows ?? 10),
    maxMoves: Number(data.max_steps ?? 30),
    numColors: Number(data.num_colors ?? 4),
    starThresholds: [1000, 3000, 5000],
    objectives: [],
    obstacleData: [],
    bottomObstacleData: [],
    blockedCells: [],   // [{x,y}]
    voidCells: [],
    prePlacedSpecials: [],
    spawnerData: [],
  };

  // goals → objectives
  const goals = data.goals || {};
  for (const tileId of Object.keys(goals)) {
    const targetCount = Number(goals[tileId]);
    const obsType = resolveObstacleType(tileId);
    if (obsType) {
      level.objectives.push({ type: 'clear_' + obsType, target: targetCount, current: 0, tile_id: tileId });
    } else {
      const colorIdx = ELEMENT_TO_COLOR_INDEX[tileId];
      if (colorIdx !== undefined) {
        level.objectives.push({ type: 'collect', color: colorIdx, target: targetCount, current: 0 });
      }
    }
  }
  if (level.objectives.length === 0) {
    level.objectives.push({ type: 'score', target: 1000, current: 0 });
  }

  const boardField = data.board;
  if (!boardField) return level;
  let middleGrid = [], upperGrid = [], bottomGrid = [], bottleColorsGrid = [];
  if (Array.isArray(boardField)) middleGrid = boardField;
  else {
    middleGrid = boardField.middle || [];
    upperGrid = boardField.upper || [];
    bottomGrid = boardField.bottom || [];
    bottleColorsGrid = boardField.bottle_colors || [];
  }

  const rows = middleGrid.length;
  const cols = level.gridWidth;
  const blockedSet = new Set();
  const sharedByKey = new Map();

  // Pass 1: middle layer
  for (let r = 0; r < rows; r++) {
    const rowData = middleGrid[r];
    if (!Array.isArray(rowData)) continue;
    for (let c = 0; c < cols; c++) {
      if (c >= rowData.length) continue;
      const rawVal = rowData[c];
      if (rawVal === null || rawVal === undefined) continue;
      const raw = String(rawVal);
      const pos = { x: c, y: r };
      if (raw === '' || raw === 'null') continue;
      if (raw === 'void') {
        level.blockedCells.push(pos);
        blockedSet.add(K(c, r));
        level.voidCells.push(pos);
        continue;
      }
      let tileId = raw, instTag = '';
      if (raw.includes('#')) {
        const parts = raw.split('#');
        tileId = parts[0];
        instTag = parts.slice(1).join('#');
      }
      if (ELEMENT_TO_COLOR_INDEX[tileId] !== undefined) continue;
      if (POWERUP_TYPE_MAP[tileId]) {
        level.prePlacedSpecials.push({ pos, type_name: POWERUP_TYPE_MAP[tileId], tile_id: tileId });
        continue;
      }
      const obsType = resolveObstacleType(tileId);
      if (obsType === null) continue;
      const hp = resolveObstacleHp(tileId);

      let bottleColor = '';
      if (bottleColorsGrid.length > r && Array.isArray(bottleColorsGrid[r])) {
        const rowBc = bottleColorsGrid[r];
        if (rowBc.length > c && rowBc[c] !== null && rowBc[c] !== undefined) bottleColor = String(rowBc[c]);
      }

      if (instTag !== '') {
        const key = tileId + '#' + instTag;
        let shared = sharedByKey.get(key);
        if (!shared) {
          shared = {
            type: obsType, hp, max_hp: hp, tile_id: tileId,
            instance_id: key, instance_cells: [], bottle_colors: {}, bottle_alive: {},
          };
          sharedByKey.set(key, shared);
        }
        shared.instance_cells.push(pos);
        if (bottleColor !== '') {
          shared.bottle_colors[K(c, r)] = bottleColor;
          shared.bottle_alive[K(c, r)] = true;
        }
        level.obstacleData.push({ pos: [pos.x, pos.y], shared_ref: shared });
      } else {
        const entry = { pos: [pos.x, pos.y], type: obsType, hp, max_hp: hp, tile_id: tileId };
        if (obsType === 'manufacturer') entry.stamp_state = 'idle';
        if (tileId.startsWith('SalmonCan')) entry.salmon_state = 'sealed';
        level.obstacleData.push(entry);
      }
      if (isBlockingObstacle(tileId)) {
        level.blockedCells.push(pos);
        blockedSet.add(K(c, r));
      }
    }
  }

  // Pass 2: upper layer (Rope/Mud)
  for (let r = 0; r < Math.min(upperGrid.length, rows); r++) {
    const rowData = upperGrid[r];
    if (!Array.isArray(rowData)) continue;
    for (let c = 0; c < cols; c++) {
      if (c >= rowData.length) continue;
      const rawVal = rowData[c];
      if (rawVal === null || rawVal === undefined) continue;
      const raw = String(rawVal);
      if (raw === '' || raw === 'null' || raw === 'void') continue;
      if (blockedSet.has(K(c, r))) continue;
      const tid = raw.split('#')[0];
      const obsType = resolveObstacleType(tid);
      if (obsType) {
        level.obstacleData.push({ pos: [c, r], type: obsType, hp: resolveObstacleHp(tid), tile_id: tid, layer: 'upper' });
        if (isBlockingObstacle(tid)) {
          level.blockedCells.push({ x: c, y: r });
          blockedSet.add(K(c, r));
        }
      }
    }
  }

  // Pass 3: bottom layer (Puddle)
  for (let r = 0; r < Math.min(bottomGrid.length, rows); r++) {
    const rowData = bottomGrid[r];
    if (!Array.isArray(rowData)) continue;
    for (let c = 0; c < cols; c++) {
      if (c >= rowData.length) continue;
      const rawVal = rowData[c];
      if (rawVal === null || rawVal === undefined) continue;
      const raw = String(rawVal);
      if (raw === '' || raw === 'null' || raw === 'void') continue;
      const tid = raw.split('#')[0];
      const obsType = resolveObstacleType(tid);
      if (obsType) {
        level.bottomObstacleData.push({ pos: [c, r], type: obsType, hp: resolveObstacleHp(tid), tile_id: tid, layer: 'bottom' });
      }
    }
  }

  // Pass 4: Spawners
  const spawnersRaw = data.spawners || [];
  if (Array.isArray(spawnersRaw)) {
    for (const s of spawnersRaw) {
      if (typeof s !== 'object' || s === null) continue;
      const spawnCols = (s.spawn_cols || []).map(Number);
      const elements = (s.elements || [])
        .filter((e) => typeof e === 'object' && e !== null)
        .map((e) => ({ tile_id: String(e.tile_id || ''), ratio: Number(e.ratio ?? 1) }));
      const setRatio = Number(s.set_ratio ?? 1);
      if (spawnCols.length > 0 && elements.length > 0) {
        level.spawnerData.push({
          spawn_cols: spawnCols, elements, set_ratio: setRatio,
          total_weight: Number(s.total_weight ?? setRatio),
        });
      }
    }
  }

  // 目標 metadata（2×2 櫃 = hits）
  for (const obj of level.objectives) {
    const tidG = String(obj.tile_id || '');
    const famG = goalFamily(tidG);
    if (famG === 'WaterChiller' || famG === 'BeverageChiller') {
      obj.board_instances = countFamilyInstances(level.obstacleData, famG);
      obj.goal_kind = 'hits';
      obj.cells_per_instance = 4;
    } else if (famG !== '') {
      obj.goal_kind = ['Barrel', 'TrafficCone', 'Stamp'].includes(famG) ? 'hits' : 'instances';
      if (famG === 'Stamp') obj.goal_kind = 'triggers';
    }
  }

  return level;
}

function countFamilyInstances(obstacleArr, family) {
  const seen = new Set();
  for (const entry of obstacleArr) {
    let tid = '', instKey = '';
    if (entry.shared_ref) {
      tid = String(entry.shared_ref.tile_id || '');
      instKey = String(entry.shared_ref.instance_id || '');
    } else {
      tid = String(entry.tile_id || '');
      instKey = String(entry.pos);
    }
    if (!tid.startsWith(family)) continue;
    if (instKey === '') instKey = String(entry.pos);
    seen.add(instKey);
  }
  return seen.size;
}

// obstacle.gd — build_obstacle_map；回傳 Map(key "x,y" → obs dict)
export function buildObstacleMap(obstacleData, gridWidth, gridHeight) {
  const obsMap = new Map();
  for (const entry of obstacleData) {
    if (!entry.pos) continue;
    const pos = { x: entry.pos[0], y: entry.pos[1] };
    if (pos.x < 0 || pos.x >= gridWidth || pos.y < 0 || pos.y >= gridHeight) continue;
    if (entry.shared_ref) {
      obsMap.set(K(pos.x, pos.y), entry.shared_ref);
      continue;
    }
    if (!entry.type) continue;
    const hp = Number(entry.hp ?? 1);
    const dataObj = { type: String(entry.type), hp, max_hp: Number(entry.max_hp ?? hp) };
    if (entry.tile_id) dataObj.tile_id = entry.tile_id;
    if (entry.layer) dataObj.layer = entry.layer;
    if (entry.stamp_state) dataObj.stamp_state = entry.stamp_state;
    if (entry.salmon_state) dataObj.salmon_state = entry.salmon_state;
    obsMap.set(K(pos.x, pos.y), dataObj);
  }
  return obsMap;
}
