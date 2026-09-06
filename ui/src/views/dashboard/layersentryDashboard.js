// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements. See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership. The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License. You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied. See the License for the
// specific language governing permissions and limitations
// under the License.

export function responseCount (response, responseKey, itemKey) {
  const body = response?.[responseKey] || {}
  const numericCount = Number(body.count)
  if (Number.isFinite(numericCount)) {
    return numericCount
  }
  const items = body?.[itemKey]
  return Array.isArray(items) ? items.length : 0
}

export function aggregateCapacity (records = []) {
  const aggregated = {}
  for (const record of Array.isArray(records) ? records : []) {
    if (!record?.name) continue
    if (!aggregated[record.name]) {
      aggregated[record.name] = {
        name: record.name,
        capacitytotal: 0,
        capacityused: 0,
        capacityallocated: 0
      }
    }
    for (const field of ['capacitytotal', 'capacityused', 'capacityallocated']) {
      const value = Number(record[field])
      if (Number.isFinite(value)) {
        aggregated[record.name][field] += value
      }
    }
  }
  return aggregated
}

export function capacityPercent (stat, field = 'capacityused') {
  const total = Number(stat?.capacitytotal)
  const value = Number(stat?.[field])
  if (!Number.isFinite(total) || total <= 0 || !Number.isFinite(value) || value < 0) {
    return 0
  }
  return Math.min(100, Math.max(0, (value / total) * 100))
}

export function hostAttentionSummary (total, up, alert) {
  const safeTotal = Number.isFinite(Number(total)) ? Number(total) : 0
  const safeUp = Number.isFinite(Number(up)) ? Number(up) : 0
  const safeAlert = Number.isFinite(Number(alert)) ? Number(alert) : 0
  return {
    total: safeTotal,
    up: safeUp,
    alert: safeAlert,
    attention: Math.max(safeAlert, Math.max(0, safeTotal - safeUp))
  }
}
