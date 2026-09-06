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

export function buildSelfServiceListParams (project, extra = {}) {
  const params = {
    listall: true,
    page: 1,
    pagesize: 1,
    ...extra
  }
  if (project?.id) params.projectid = project.id
  return params
}

export function buildSelfServiceRouteQuery (project, extra = {}) {
  const query = { ...extra }
  if (project?.id) query.projectid = project.id
  return query
}

export function countResponse (response, responseKey, itemKey) {
  const body = response?.[responseKey] || {}
  const count = Number(body.count)
  if (Number.isFinite(count)) return count
  const items = body[itemKey]
  return Array.isArray(items) ? items.length : 0
}
