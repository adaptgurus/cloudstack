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

import { vueProps } from '@/vue-app'

export const LAYERSENTRY_KVM_PROFILE = 'layersentry-kvm'

export function isLayersentryKvmProfile (config = vueProps.$config) {
  return config?.productProfile === LAYERSENTRY_KVM_PROFILE
}

export function filterProductHypervisors (hypervisors, config = vueProps.$config) {
  const availableHypervisors = Array.isArray(hypervisors) ? hypervisors : []
  if (!isLayersentryKvmProfile(config)) {
    return availableHypervisors
  }
  return availableHypervisors.filter(hypervisor => {
    const name = typeof hypervisor === 'string' ? hypervisor : hypervisor?.name
    return name === 'KVM'
  })
}

export function filterProductImages (images, isIso = false, config = vueProps.$config) {
  const available = Array.isArray(images) ? images : []
  if (!isLayersentryKvmProfile(config)) return available
  return available.filter(image => image?.hypervisor === 'KVM' ||
    (isIso && image?.hypervisor === 'None'))
}
