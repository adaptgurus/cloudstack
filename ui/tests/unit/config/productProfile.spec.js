// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.

import {
  filterProductHypervisors,
  isLayersentryKvmProfile,
  LAYERSENTRY_KVM_PROFILE
} from '@/config/productProfile'

describe('LayerSentry product profile', () => {
  const profile = { productProfile: LAYERSENTRY_KVM_PROFILE }

  it('recognizes only the explicit LayerSentry KVM profile', () => {
    expect(isLayersentryKvmProfile(profile)).toBe(true)
    expect(isLayersentryKvmProfile({ productProfile: 'cloudstack' })).toBe(false)
    expect(isLayersentryKvmProfile({})).toBe(false)
  })

  it('keeps only KVM object choices in the LayerSentry profile', () => {
    const choices = [{ name: 'VMware' }, { name: 'KVM' }, { name: 'Simulator' }]
    expect(filterProductHypervisors(choices, profile)).toEqual([{ name: 'KVM' }])
  })

  it('keeps only KVM string choices in the LayerSentry profile', () => {
    expect(filterProductHypervisors(['Any', 'KVM', 'Hyperv'], profile)).toEqual(['KVM'])
  })

  it('preserves upstream choices when no product profile is selected', () => {
    const choices = [{ name: 'KVM' }, { name: 'VMware' }]
    expect(filterProductHypervisors(choices, {})).toBe(choices)
  })

  it('fails safely for a missing hypervisor response', () => {
    expect(filterProductHypervisors(undefined, profile)).toEqual([])
  })
})
