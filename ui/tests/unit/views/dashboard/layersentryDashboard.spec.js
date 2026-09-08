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

import {
  aggregateCapacity,
  capacityPercent,
  hostAttentionSummary,
  responseCount
} from '@/views/dashboard/layersentryDashboard'

describe('LayerSentry platform dashboard helpers', () => {
  it('extracts API counts without requiring resource arrays', () => {
    expect(responseCount({ listzonesresponse: { count: 3 } }, 'listzonesresponse', 'zone')).toBe(3)
    expect(responseCount({ listzonesresponse: { zone: [{}, {}] } }, 'listzonesresponse', 'zone')).toBe(2)
    expect(responseCount({}, 'listzonesresponse', 'zone')).toBe(0)
  })

  it('aggregates capacity records across sites and scopes', () => {
    expect(aggregateCapacity([
      { name: 'MEMORY', capacitytotal: 100, capacityused: 40, capacityallocated: 60 },
      { name: 'MEMORY', capacitytotal: 200, capacityused: 50, capacityallocated: 80 },
      { name: 'CPU_CORE', capacitytotal: 20, capacityused: 5 }
    ])).toEqual({
      MEMORY: {
        name: 'MEMORY',
        capacitytotal: 300,
        capacityused: 90,
        capacityallocated: 140
      },
      CPU_CORE: {
        name: 'CPU_CORE',
        capacitytotal: 20,
        capacityused: 5,
        capacityallocated: 0
      }
    })
  })

  it('returns bounded percentages for incomplete capacity data', () => {
    expect(capacityPercent({ capacitytotal: 100, capacityused: 25 })).toBe(25)
    expect(capacityPercent({ capacitytotal: 100, capacityused: 140 })).toBe(100)
    expect(capacityPercent({ capacitytotal: 0, capacityused: 10 })).toBe(0)
    expect(capacityPercent(undefined)).toBe(0)
  })

  it('treats both alert state and non-Up hosts as attention items', () => {
    expect(hostAttentionSummary(10, 9, 0)).toEqual({ total: 10, up: 9, alert: 0, attention: 1 })
    expect(hostAttentionSummary(10, 10, 2)).toEqual({ total: 10, up: 10, alert: 2, attention: 2 })
    expect(hostAttentionSummary(undefined, undefined, undefined)).toEqual({ total: 0, up: 0, alert: 0, attention: 0 })
  })
})
