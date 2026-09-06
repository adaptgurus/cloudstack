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

<template>
  <main class="exception" :aria-labelledby="`layersentry-error-${type}`">
    <div class="exception__image" v-if="$config.error[type]">
      <img
        :src="$config.error[type]"
        alt=""
        role="presentation"
        :style="{
          width: $config.theme['@error-width'],
          height: $config.theme['@error-height']
        }" />
    </div>
    <section class="exception__content">
      <div class="exception__brand">LAYERSENTRY · {{ config[type].code }}</div>
      <h1 :id="`layersentry-error-${type}`">{{ config[type].title }}</h1>
      <p class="exception__desc">{{ config[type].desc }}</p>
      <div class="exception__actions">
        <a-button v-if="canGoBack" @click="handleBack">{{ $t('label.go.back') }}</a-button>
        <a-button type="primary" @click="handleToHome">{{ $t('label.dashboard') }}</a-button>
      </div>
    </section>
  </main>
</template>

<script>
import types from './type'

export default {
  name: 'Exception',
  props: {
    type: {
      type: String,
      default: '404',
      validator: value => Object.prototype.hasOwnProperty.call(types, value)
    }
  },
  data () {
    return {
      config: types
    }
  },
  computed: {
    canGoBack () {
      return typeof window !== 'undefined' && window.history.length > 1
    }
  },
  methods: {
    handleBack () {
      this.$router.back()
    },
    handleToHome () {
      this.$router.push({ name: 'dashboard' })
    }
  }
}
</script>

<style lang="less" scoped>
.exception {
  min-height: 65vh;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 48px;
  max-width: 1100px;
  margin: 0 auto;
  padding: 48px 24px;

  &__image {
    flex: 0 1 auto;

    img {
      max-width: min(320px, 38vw);
      height: auto !important;
      object-fit: contain;
    }
  }

  &__content {
    max-width: 560px;
    text-align: left;
  }

  &__brand {
    margin-bottom: 8px;
    color: #0f766e;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: .12em;
  }

  h1 {
    margin: 0 0 12px;
    color: #101828;
    font-size: clamp(32px, 5vw, 52px);
    font-weight: 650;
    line-height: 1.1;
  }

  &__desc {
    margin: 0;
    color: #667085;
    font-size: 16px;
    line-height: 1.65;
  }

  &__actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 24px;
  }
}

@media (max-width: 760px) {
  .exception {
    flex-direction: column;
    gap: 24px;
    padding-top: 28px;
    text-align: center;

    &__content { text-align: center; }
    &__actions { justify-content: center; }
    &__image img { max-width: 210px; }
  }
}
</style>
