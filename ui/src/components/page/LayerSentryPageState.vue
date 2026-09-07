<!--
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements. See the NOTICE file
distributed with this work for additional information
regarding copyright ownership. The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License. You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied. See the License for the
specific language governing permissions and limitations
under the License.
-->
<template>
  <section class="ls-page-state" :aria-busy="loading" aria-live="polite">
    <div class="ls-page-state__identity">
      <div>
        <h1>{{ title }}</h1>
        <p>{{ description }}</p>
      </div>
      <a-tag v-if="updatedAt">{{ $t('label.layersentry.last.updated') }}: {{ $toLocaleDate(updatedAt) }}</a-tag>
    </div>
    <a-alert v-if="failure" :type="failure.status === 'forbidden' ? 'warning' : 'error'" show-icon>
      <template #message>{{ $t(failure.status === 'forbidden' ? 'label.layersentry.read.denied' : 'label.layersentry.read.failed') }}</template>
      <template #description>
        <p>{{ $t(hasData ? 'message.layersentry.stale.data' : 'message.layersentry.read.failed') }}</p>
        <p v-if="failure.message" class="ls-page-state__diagnostic">{{ failure.message }}</p>
        <p v-if="failure.code || failure.requestId" class="ls-page-state__diagnostic">
          <span v-if="failure.code">{{ $t('label.layersentry.response.code') }}: {{ failure.code }} </span>
          <span v-if="failure.requestId">{{ $t('label.id') }}: {{ failure.requestId }}</span>
        </p>
        <a-button :loading="loading" @click="$emit('retry')">{{ $t('label.refresh') }}</a-button>
      </template>
    </a-alert>
    <div v-else-if="loading" role="status" class="ls-page-state__message">
      <a-spin size="small" /> {{ $t('label.loading') }}
    </div>
    <div v-else-if="empty" class="ls-page-state__message">
      <strong>{{ $t('label.layersentry.no.matches') }}</strong>
      <p>{{ $t('message.layersentry.no.matches') }}</p>
      <a-button @click="$emit('retry')">{{ $t('label.refresh') }}</a-button>
    </div>
  </section>
</template>

<script>
export default {
  name: 'LayerSentryPageState',
  emits: ['retry'],
  props: {
    title: { type: String, required: true },
    description: { type: String, default: '' },
    loading: Boolean,
    empty: Boolean,
    hasData: Boolean,
    failure: { type: Object, default: null },
    updatedAt: { type: String, default: '' }
  }
}
</script>

<style lang="less" scoped>
.ls-page-state {
  margin: 16px 0;
  padding: 20px;
  border: 1px solid var(--ls-border-subtle);
  border-radius: var(--ls-radius-lg);
  background: var(--ls-surface);
  color: var(--ls-text);
  h1 { margin: 0 0 8px; font-size: 22px; overflow-wrap: anywhere; }
  p { margin: 8px 0; }
  &__identity { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
  &__diagnostic { white-space: pre-wrap; overflow-wrap: anywhere; }
  &__message { margin-top: 12px; }
}
</style>
