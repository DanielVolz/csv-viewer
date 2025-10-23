const CATEGORY_DEFINITIONS = [
  {
    id: 'meta',
    label: 'General',
    values: ['#', 'File Name', 'Creation Date']
  },
  {
    id: 'network',
    label: 'Network',
    values: [
      'IP Address',
      'MAC Address',
      'MAC Address 2',
      'Subnet Mask',
      'Voice VLAN',
      'Switch Hostname',
      'Switch Port'
    ],
    patterns: [
      /\bip\b/i,
      /vlan/i,
      /mac/i,
      /subnet/i,
      /switch/i,
      /network/i,
      /qos/i
    ]
  },
  {
    id: 'networkSpeed',
    label: 'Network Speed',
    values: [
      'Switch Port Mode',
      'PC Port Mode',
      'Phone Port Speed',
      'PC Port Speed',
      'Port Auto Link Sync',
      'SW Port Remote Config',
      'PC Port Remote Config'
    ],
    patterns: [
      /port\s+(mode|speed)/i,
      /auto\s*link/i,
      /remote\s+config/i,
      /speed/i
    ]
  },
  {
    id: 'device',
    label: 'Device',
    values: [
      'Serial Number',
      'Model Name',
      'Product ID',
      'Phone Description',
      'Device Name',
      'Line Number',
      'Active Load ID',
      'Inactive Load ID',
      'KEM 1 Serial',
      'KEM 2 Serial'
    ],
    patterns: [
      /serial/i,
      /model/i,
      /device/i,
      /product/i,
      /phone/i,
      /load/i,
      /firmware/i,
      /hardware/i,
      /kem/i,
      /module/i
    ]
  },
  {
    id: 'callManager',
    label: 'Call Manager',
    values: [
      'Call Manager Active Sub',
      'Call Manager Standby Sub',
      'Device Pool',
      'Directory Number',
      'Primary CSS',
      'AAR Group',
      'AAR CSS'
    ],
    patterns: [
      /call manager/i,
      /directory/i,
      /line/i,
      /partition/i,
      /css/i,
      /device pool/i,
      /translation/i,
      /route/i,
      /profile/i
    ]
  },
  {
    id: 'location',
    label: 'Location',
    values: [
      'Site',
      'Campus',
      'Building',
      'Floor',
      'Room',
      'Location'
    ],
    patterns: [
      /site/i,
      /campus/i,
      /building/i,
      /floor/i,
      /room/i,
      /location/i,
      /region/i
    ]
  },
  {
    id: 'ownership',
    label: 'Ownership',
    values: [
      'Owner User ID',
      'Owner Display Name',
      'Department',
      'Cost Center',
      'Contact'
    ],
    patterns: [
      /owner/i,
      /user/i,
      /department/i,
      /cost/i,
      /manager/i,
      /contact/i
    ]
  }
];

const FALLBACK_CATEGORY = 'other';
const FALLBACK_LABEL = 'Other';

const exactMatchLookup = new Map();
CATEGORY_DEFINITIONS.forEach((definition) => {
  if (!definition.values) return;
  definition.values.forEach((value) => {
    exactMatchLookup.set(value, definition.id);
  });
});

export const CATEGORY_ORDER = CATEGORY_DEFINITIONS.map((definition) => definition.id);

export const CATEGORY_LABELS = CATEGORY_DEFINITIONS.reduce((acc, definition) => {
  acc[definition.id] = definition.label;
  return acc;
}, { [FALLBACK_CATEGORY]: FALLBACK_LABEL });

export function getColumnCategory(columnId) {
  if (!columnId) {
    return FALLBACK_CATEGORY;
  }
  const exactMatch = exactMatchLookup.get(columnId);
  if (exactMatch) {
    return exactMatch;
  }
  for (const definition of CATEGORY_DEFINITIONS) {
    if (!definition.patterns) {
      continue;
    }
    if (definition.patterns.some((pattern) => pattern.test(columnId))) {
      return definition.id;
    }
  }
  return FALLBACK_CATEGORY;
}

export function getCategoryLabel(categoryId) {
  return CATEGORY_LABELS[categoryId] || FALLBACK_LABEL;
}