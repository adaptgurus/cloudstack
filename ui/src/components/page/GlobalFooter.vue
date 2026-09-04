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

<template>
  <div class="footer">
    <div class="product">{{ $config.footer || 'Layersentry V1.0' }}</div>
    <div class="tagline">Secure cloud infrastructure management</div>
  </div>
</template>

<script>
export default {
  name: 'LayoutFooter'
}
</script>

<style lang="less" scoped>
  .footer {
    padding: 0 16px;
    margin: 32px 0 20px;
    text-align: center;
    color: #667085;
  }

  .product {
    color: #344054;
    font-weight: 600;
    margin-bottom: 4px;
  }

  .tagline {
    font-size: 12px;
  }
</style>
