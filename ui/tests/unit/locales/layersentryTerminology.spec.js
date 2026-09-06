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

import { layersentryEnglishTerminology } from '@/locales'

describe('LayerSentry customer terminology', () => {
  it('maps exact CloudStack infrastructure concepts to LayerSentry product language', () => {
    expect(layersentryEnglishTerminology['label.zone']).toBe('Site')
    expect(layersentryEnglishTerminology['label.pod']).toBe('Infrastructure Group')
    expect(layersentryEnglishTerminology['label.domain']).toBe('Department')
    expect(layersentryEnglishTerminology['label.host']).toBe('KVM Host')
    expect(layersentryEnglishTerminology['label.service.offering']).toBe('Compute Profile')
    expect(layersentryEnglishTerminology['label.diskoffering']).toBe('Storage Profile')
    expect(layersentryEnglishTerminology['label.template']).toBe('OS Image')
  })

  it('does not globally rename ambiguous cluster terminology', () => {
    expect(layersentryEnglishTerminology['label.cluster']).toBeUndefined()
    expect(layersentryEnglishTerminology['label.layersentry.compute.clusters']).toBe('Compute Clusters')
  })
})
