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

import types from '@/views/exception/type'

describe('LayerSentry exception copy', () => {
  it('keeps exact status codes while using product-safe recovery language', () => {
    expect(types['403'].code).toBe('403')
    expect(types['404'].code).toBe('404')
    expect(types['500'].code).toBe('500')
    expect(types['403'].desc).toContain('LayerSentry')
    expect(types['404'].desc).toContain('LayerSentry')
    expect(types['500'].desc).toContain('LayerSentry')
  })
})
