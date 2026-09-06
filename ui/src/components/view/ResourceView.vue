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
  <resource-layout>
    <template #left>
      <slot name="info-card">
        <info-card :resource="resource" :loading="loading" />
      </slot>
    </template>
    <template #right>
      <a-card
        class="spin-content"
        :loading="loading"
        :bordered="true"
        style="width:100%">
        <a-alert v-if="networkError" type="warning" show-icon :message="$t('label.layersentry.read.failed')">
          <template #description>
            <p>{{ $t('message.layersentry.network.tabs') }}</p>
            <p style="overflow-wrap: anywhere">{{ networkError.code }} {{ networkError.message }}</p>
            <a-button @click="fetchData">{{ $t('label.refresh') }}</a-button>
          </template>
        </a-alert>
        <a-empty v-if="!visibleTabs.length && !loading" :description="$t('message.layersentry.no.detail.tabs')" />
        <keep-alive v-if="visibleTabs.length === 1">
          <component
            :is="visibleTabs[0].component"
            :resource="resource"
            :resourceType="visibleTabs[0].resourceType"
            :loading="loading"
            :tab="tabName(visibleTabs[0])" />
        </keep-alive>
        <a-tabs
          v-else-if="visibleTabs.length > 1"
          style="width: 100%; margin-top: -12px"
          :animated="false"
          :activeKey="activeTab || tabName(visibleTabs[0])"
          @change="onTabChange" >
          <template v-for="tab in visibleTabs" :key="tabName(tab)">
            <a-tab-pane
              :key="tabName(tab)"
              :tab="$t('label.' + tabName(tab))"
              v-if="showTab(tab)">
              <keep-alive>
                <component
                  v-if="tab.resourceType"
                  :is="tab.component"
                  :resource="resource"
                  :resourceType="tab.resourceType"
                  :loading="loading"
                  :tab="activeTab" />
                <component v-else :is="tab.component" :resource="resource" :loading="loading" :tab="activeTab" />
              </keep-alive>
            </a-tab-pane>
          </template>
        </a-tabs>
      </a-card>
    </template>
  </resource-layout>
</template>

<script>
import DetailsTab from '@/components/view/DetailsTab'
import InfoCard from '@/components/view/InfoCard'
import ResourceLayout from '@/layouts/ResourceLayout'
import { getAPI } from '@/api'
import { mixinDevice } from '@/utils/mixin.js'
import { readFailure } from '@/config/layersentryPage'

export default {
  name: 'ResourceView',
  components: {
    InfoCard,
    ResourceLayout
  },
  mixins: [mixinDevice],
  props: {
    resource: {
      type: Object,
      required: true
    },
    loading: {
      type: Boolean,
      default: false
    },
    tabs: {
      type: Array,
      default: function () {
        return [{
          name: 'details',
          component: DetailsTab
        }]
      }
    },
    historyTab: {
      type: String,
      default: ''
    }
  },
  data () {
    return {
      activeTab: '',
      networkService: null,
      networkError: null,
      networkGeneration: 0,
      projectAccount: null
    }
  },
  watch: {
    resource: {
      deep: true,
      handler (newItem, oldItem) {
        if (newItem.id === oldItem.id && newItem.associatednetworkid === oldItem.associatednetworkid) return

        this.fetchData()
      }
    },
    '$route.fullPath': function () {
      this.setActiveTab()
    },
    tabs: {
      handler () {
        this.setActiveTab()
      }
    },
    visibleTabs () {
      this.setActiveTab()
    }
  },
  computed: {
    visibleTabs () {
      return this.tabs.filter(tab => this.showTab(tab))
    }
  },
  created () {
    this.setActiveTab()
    window.addEventListener('popstate', this.setActiveTab)
    this.fetchData()
  },
  beforeUnmount () {
    this.networkGeneration++
    window.removeEventListener('popstate', this.setActiveTab)
  },
  methods: {
    fetchData () {
      const generation = ++this.networkGeneration
      this.networkService = null
      this.networkError = null
      if (this.resource.associatednetworkid) {
        getAPI('listNetworks', { id: this.resource.associatednetworkid, listall: true }).then(response => {
          if (generation !== this.networkGeneration) return
          if (response && response.listnetworksresponse && response.listnetworksresponse.network) {
            this.networkService = response.listnetworksresponse.network[0]
          } else {
            this.networkService = {}
          }
        }).catch(error => {
          if (generation === this.networkGeneration) this.networkError = readFailure(error)
        })
      }
    },
    onTabChange (key) {
      this.activeTab = key
      const query = Object.assign({}, this.$route.query)
      query.tab = key
      this.$route.query.tab = key
      history.pushState(
        {},
        null,
        '#' + this.$route.path + '?' + Object.keys(query).map(key => {
          return (
            encodeURIComponent(key) + '=' + encodeURIComponent(query[key])
          )
        }).join('&')
      )
      this.$emit('onTabChange', key)
    },
    tabName (tab) {
      if (!tab) return ''
      if (typeof tab.name === 'function') {
        return tab.name(this.resource)
      }
      return tab.name
    },
    showTab (tab) {
      if (this.networkService && this.networkService.service && tab.networkServiceFilter) {
        return tab.networkServiceFilter(this.networkService.service)
      } else if ('show' in tab) {
        return tab.show(this.resource, this.$route, this.$store.getters.userInfo)
      } else {
        return true
      }
    },
    setActiveTab () {
      const names = this.visibleTabs.map(tab => this.tabName(tab))
      const requested = this.$route.query.tab || this.historyTab
      this.activeTab = names.includes(requested) ? requested : (names[0] || '')
    }
  }
}
</script>

<style lang="less" scoped>
</style>
