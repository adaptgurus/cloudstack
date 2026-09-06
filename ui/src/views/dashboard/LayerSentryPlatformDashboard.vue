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
  <div class="ls-platform-dashboard">
    <section class="ls-dashboard-hero" aria-labelledby="layersentry-platform-dashboard-title">
      <div class="ls-dashboard-hero__copy">
        <div class="ls-eyebrow">{{ $t('label.layersentry.platform.operations') }}</div>
        <h1 id="layersentry-platform-dashboard-title">{{ $t('label.dashboard') }}</h1>
        <p>{{ $t('message.layersentry.platform.dashboard') }}</p>
      </div>
      <div class="ls-dashboard-hero__actions">
        <a-select
          v-if="hasApi('listZones')"
          v-model:value="selectedSiteId"
          :options="siteOptions"
          :loading="loadingSites"
          :disabled="refreshing || scopedLoading"
          show-search
          option-filter-prop="label"
          class="ls-site-selector"
          :aria-label="$t('label.zone')"
          @change="refreshScopedData" />
        <router-link v-if="quickProvisionVisible" :to="{ path: '/quick-provision' }">
          <a-button type="primary">
            <rocket-outlined />
            {{ $t('label.layersentry.quick.provision') }}
          </a-button>
        </router-link>
        <a-button :loading="refreshing || scopedLoading" :aria-label="$t('label.refresh')" @click="refresh">
          <reload-outlined />
          {{ $t('label.refresh') }}
        </a-button>
      </div>
    </section>

    <a-alert
      v-if="fatalError"
      type="error"
      show-icon
      class="ls-dashboard-alert"
      :message="fatalError" />

    <a-alert
      v-else-if="partialFailures.length"
      type="warning"
      show-icon
      class="ls-dashboard-alert"
      :message="$t('label.layersentry.partial.data', { sections: partialFailures.join(', ') })" />

    <a-row :gutter="[16, 16]" class="ls-summary-grid">
      <a-col
        v-for="card in summaryCards"
        :key="card.key"
        :xs="24"
        :sm="12"
        :xl="8"
        :xxl="4">
        <router-link :to="card.to" class="ls-summary-link">
          <a-card :bordered="false" class="ls-summary-card">
            <div class="ls-summary-card__top">
              <span class="ls-summary-card__icon"><component :is="card.icon" /></span>
              <a-tag v-if="card.badge" :color="card.badgeColor || 'default'">{{ card.badge }}</a-tag>
            </div>
            <div class="ls-summary-card__value">{{ displayCount(card.value) }}</div>
            <div class="ls-summary-card__label">{{ card.label }}</div>
            <div v-if="card.detail" class="ls-summary-card__detail">{{ card.detail }}</div>
          </a-card>
        </router-link>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]" class="ls-dashboard-row">
      <a-col :xs="24" :xl="16">
        <a-card :bordered="false" class="ls-dashboard-card">
          <template #title>
            <div class="ls-card-title">
              <dashboard-outlined />
              <span>{{ $t('label.layersentry.capacity') }}</span>
            </div>
          </template>
          <template #extra>
            <span class="ls-scope-label">{{ selectedSiteLabel }}</span>
          </template>

          <div v-if="!hasApi('listCapacity')" class="ls-inline-empty">
            {{ $t('label.layersentry.unavailable') }}
          </div>
          <div v-else-if="loadingCapacity" class="ls-capacity-skeleton">
            <a-skeleton active :paragraph="{ rows: 4 }" />
          </div>
          <div v-else-if="capacityRows.length === 0" class="ls-inline-empty">
            {{ $t('label.layersentry.no.capacity') }}
          </div>
          <div v-else class="ls-capacity-list">
            <div v-for="row in capacityRows" :key="row.key" class="ls-capacity-row">
              <div class="ls-capacity-row__header">
                <strong>{{ row.label }}</strong>
                <span>{{ row.used }} / {{ row.total }}</span>
              </div>
              <a-progress
                :percent="row.percent"
                :status="row.percent >= 90 ? 'exception' : 'normal'"
                :format="percent => `${percent.toFixed(0)}%`" />
            </div>
          </div>
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="8">
        <a-card :bordered="false" class="ls-dashboard-card ls-service-card">
          <template #title>
            <div class="ls-card-title">
              <safety-certificate-outlined />
              <span>{{ $t('label.layersentry.protection.services') }}</span>
            </div>
          </template>

          <div class="ls-service-list">
            <div v-for="service in serviceFacts" :key="service.key" class="ls-service-row">
              <div>
                <strong>{{ service.label }}</strong>
                <div class="ls-service-row__hint">{{ service.hint }}</div>
              </div>
              <a-tag :color="service.color">{{ service.value }}</a-tag>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]" class="ls-dashboard-row">
      <a-col :xs="24" :xl="12">
        <a-card :bordered="false" class="ls-dashboard-card ls-feed-card">
          <template #title>
            <div class="ls-card-title">
              <warning-outlined />
              <span>{{ $t('label.layersentry.recent.alerts') }}</span>
            </div>
          </template>
          <template #extra>
            <router-link v-if="hasApi('listAlerts')" :to="{ path: '/alert' }">{{ $t('label.view') }}</router-link>
          </template>

          <div v-if="loadingAlerts" class="ls-feed-loading"><a-spin /></div>
          <div v-else-if="!hasApi('listAlerts')" class="ls-inline-empty">{{ $t('label.layersentry.unavailable') }}</div>
          <a-alert v-else-if="alertsFailed" type="warning" show-icon :message="$t('label.layersentry.read.failed')" :description="$t('message.layersentry.read.failed')" />
          <div v-else-if="alerts.length === 0" class="ls-inline-empty">{{ $t('label.layersentry.no.alerts') }}</div>
          <div v-else class="ls-feed-list">
            <router-link
              v-for="alert in alerts"
              :key="alert.id"
              :to="{ path: `/alert/${alert.id}` }"
              class="ls-feed-row">
              <span class="ls-feed-row__marker ls-feed-row__marker--alert"></span>
              <span class="ls-feed-row__content">
                <strong>{{ alert.name || alert.type || $t('label.alert') }}</strong>
                <small>{{ alert.sent ? $toLocaleDate(alert.sent) : '' }}</small>
                <span>{{ alert.description || '' }}</span>
              </span>
            </router-link>
          </div>
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="12">
        <a-card :bordered="false" class="ls-dashboard-card ls-feed-card">
          <template #title>
            <div class="ls-card-title">
              <schedule-outlined />
              <span>{{ $t('label.layersentry.recent.activity') }}</span>
            </div>
          </template>
          <template #extra>
            <router-link v-if="hasApi('listEvents')" :to="{ path: '/event' }">{{ $t('label.view') }}</router-link>
          </template>

          <div v-if="loadingEvents" class="ls-feed-loading"><a-spin /></div>
          <div v-else-if="!hasApi('listEvents')" class="ls-inline-empty">{{ $t('label.layersentry.unavailable') }}</div>
          <a-alert v-else-if="eventsFailed" type="warning" show-icon :message="$t('label.layersentry.read.failed')" :description="$t('message.layersentry.read.failed')" />
          <div v-else-if="events.length === 0" class="ls-inline-empty">{{ $t('label.layersentry.no.events') }}</div>
          <div v-else class="ls-feed-list">
            <router-link
              v-for="event in events"
              :key="event.id"
              :to="{ path: `/event/${event.id}` }"
              class="ls-feed-row">
              <span :class="['ls-feed-row__marker', eventMarkerClass(event)]"></span>
              <span class="ls-feed-row__content">
                <strong>{{ event.type || $t('label.event') }}</strong>
                <small>{{ event.created ? $toLocaleDate(event.created) : '' }}</small>
                <span>{{ event.description || event.state || '' }}</span>
              </span>
            </router-link>
          </div>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script>
import {
  ApartmentOutlined,
  CloudServerOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  GlobalOutlined,
  HddOutlined,
  ReloadOutlined,
  RocketOutlined,
  SafetyCertificateOutlined,
  ScheduleOutlined,
  ThunderboltOutlined,
  WarningOutlined
} from '@ant-design/icons-vue'
import { getAPI } from '@/api'
import {
  getLayersentryCapabilities,
  hasApi as apiGranted,
  LAYERSENTRY_FEATURES
} from '@/config/layersentryCapabilities'
import {
  aggregateCapacity,
  capacityPercent,
  hostAttentionSummary,
  responseCount
} from './layersentryDashboard'

const ALL_SITES = '__all_sites__'

export default {
  name: 'LayerSentryPlatformDashboard',
  components: {
    ApartmentOutlined,
    CloudServerOutlined,
    DashboardOutlined,
    DatabaseOutlined,
    GlobalOutlined,
    HddOutlined,
    ReloadOutlined,
    RocketOutlined,
    SafetyCertificateOutlined,
    ScheduleOutlined,
    ThunderboltOutlined,
    WarningOutlined
  },
  data () {
    return {
      sites: [],
      selectedSiteId: ALL_SITES,
      refreshing: false,
      scopedLoading: false,
      loadingSites: false,
      loadingCapacity: false,
      loadingAlerts: false,
      loadingEvents: false,
      eventsFailed: false,
      alertsFailed: false,
      fatalError: '',
      partialFailures: [],
      counts: {
        instances: null,
        hosts: null,
        hostsUp: null,
        hostsAlert: null,
        storagePools: null,
        networks: null,
        computeClusters: null,
        infrastructureGroups: null,
        platformServices: null,
        backupOfferings: null,
        nativeKubernetes: null,
        buckets: null
      },
      capacityMap: {},
      alerts: [],
      events: []
    }
  },
  computed: {
    capabilities () {
      return getLayersentryCapabilities(this.$store.getters.apis, this.$config)
    },
    quickProvisionVisible () {
      return this.capabilities[LAYERSENTRY_FEATURES.QUICK_PROVISION]?.visible === true
    },
    nativeKubernetesVisible () {
      return this.capabilities[LAYERSENTRY_FEATURES.NATIVE_KUBERNETES]?.visible === true
    },
    siteOptions () {
      return [
        { label: this.$t('label.layersentry.all.sites'), value: ALL_SITES },
        ...this.sites.map(site => ({ label: site.name, value: site.id }))
      ]
    },
    selectedSite () {
      return this.sites.find(site => site.id === this.selectedSiteId)
    },
    selectedSiteLabel () {
      return this.selectedSite?.name || this.$t('label.layersentry.all.sites')
    },
    hostSummary () {
      return hostAttentionSummary(this.counts.hosts, this.counts.hostsUp, this.counts.hostsAlert)
    },
    summaryCards () {
      const cards = []
      if (this.hasApi('listVirtualMachines')) {
        cards.push({
          key: 'instances',
          label: this.$t('label.instances'),
          value: this.counts.instances,
          icon: CloudServerOutlined,
          to: { path: '/vm', query: { hypervisor: 'KVM', ...this.routeScopeQuery() } },
          badge: 'KVM',
          badgeColor: 'green',
          detail: this.selectedSiteLabel
        })
      }
      if (this.hasApi('listHosts')) {
        cards.push({
          key: 'hosts',
          label: this.$t('label.layersentry.kvm.hosts'),
          value: this.counts.hosts,
          icon: DatabaseOutlined,
          to: { path: '/host', query: { hypervisor: 'KVM', ...this.routeScopeQuery() } },
          badge: this.hostSummary.attention > 0
            ? this.$t('label.layersentry.attention.required')
            : (this.counts.hosts === null ? null : `${this.hostSummary.up} Up`),
          badgeColor: this.hostSummary.attention > 0 ? 'red' : 'green',
          detail: this.counts.hosts === null
            ? this.$t('label.layersentry.unavailable')
            : `${this.hostSummary.attention} ${this.$t('label.layersentry.host.exceptions')}`
        })
      }
      if (this.hasApi('listStoragePools')) {
        cards.push({
          key: 'storage',
          label: this.$t('label.layersentry.storage.pools'),
          value: this.counts.storagePools,
          icon: HddOutlined,
          to: { path: '/storagepool', query: this.routeScopeQuery() },
          detail: this.selectedSiteLabel
        })
      }
      if (this.hasApi('listNetworks')) {
        cards.push({
          key: 'networks',
          label: this.$t('label.network'),
          value: this.counts.networks,
          icon: ApartmentOutlined,
          to: { path: '/guestnetwork', query: this.routeScopeQuery() },
          detail: this.selectedSiteLabel
        })
      }
      if (this.hasApi('listClusters')) {
        cards.push({
          key: 'clusters',
          label: this.$t('label.layersentry.compute.clusters'),
          value: this.counts.computeClusters,
          icon: ThunderboltOutlined,
          to: { path: '/cluster', query: { hypervisor: 'KVM', ...this.routeScopeQuery() } },
          detail: this.selectedSiteLabel
        })
      }
      if (this.hasApi('listZones')) {
        cards.push({
          key: 'sites',
          label: this.$t('label.zones'),
          value: this.sites.length,
          icon: GlobalOutlined,
          to: { path: '/zone' },
          detail: this.$t('label.layersentry.infrastructure.groups') + ': ' + this.displayCount(this.counts.infrastructureGroups)
        })
      }
      return cards
    },
    capacityRows () {
      const definitions = [
        { key: 'CPU_CORE', label: this.$t('label.cpunumber') },
        { key: 'MEMORY', label: this.$t('label.memory') },
        { key: 'STORAGE', label: this.$t('label.primary.storage') }
      ]
      return definitions
        .filter(definition => this.capacityMap[definition.key])
        .map(definition => {
          const stat = this.capacityMap[definition.key]
          return {
            ...definition,
            percent: capacityPercent(stat),
            used: this.formatCapacityValue(definition.key, stat.capacityused),
            total: this.formatCapacityValue(definition.key, stat.capacitytotal)
          }
        })
    },
    serviceFacts () {
      const facts = []
      if (this.hasApi('listBackupOfferings')) {
        facts.push({
          key: 'backup',
          label: this.$t('label.backup'),
          value: this.counts.backupOfferings === null
            ? this.$t('label.layersentry.unavailable')
            : (this.counts.backupOfferings > 0
                ? `${this.counts.backupOfferings} ${this.$t('label.layersentry.offerings.available')}`
                : this.$t('label.layersentry.not.configured')),
          hint: this.$t('message.layersentry.backup.dashboard.fact'),
          color: this.counts.backupOfferings > 0 ? 'blue' : 'default'
        })
      }
      if (this.nativeKubernetesVisible) {
        facts.push({
          key: 'native-kubernetes',
          label: this.$t('label.kubernetes'),
          value: this.counts.nativeKubernetes === null
            ? this.$t('label.layersentry.unavailable')
            : `${this.counts.nativeKubernetes} ${this.$t('label.kubernetes.cluster')}`,
          hint: this.$t('message.layersentry.native.kubernetes.dashboard.fact'),
          color: 'blue'
        })
      }
      if (this.hasApi('listBuckets')) {
        facts.push({
          key: 'buckets',
          label: this.$t('label.buckets'),
          value: this.counts.buckets === null
            ? this.$t('label.layersentry.unavailable')
            : String(this.counts.buckets),
          hint: this.$t('message.layersentry.bucket.dashboard.fact'),
          color: 'default'
        })
      }
      if (facts.length === 0) {
        facts.push({
          key: 'none',
          label: this.$t('label.layersentry.optional.services'),
          value: this.$t('label.layersentry.unavailable'),
          hint: this.$t('message.layersentry.optional.services.unavailable'),
          color: 'default'
        })
      }
      return facts
    }
  },
  created () {
    this.refresh()
  },
  methods: {
    hasApi (api) {
      return apiGranted(this.$store.getters.apis, api)
    },
    displayCount (value) {
      return value === null || value === undefined ? '—' : value
    },
    scopedParams () {
      return this.selectedSiteId === ALL_SITES ? {} : { zoneid: this.selectedSiteId }
    },
    routeScopeQuery () {
      return this.selectedSiteId === ALL_SITES ? {} : { zoneid: this.selectedSiteId }
    },
    async runSection (label, callback) {
      try {
        await callback()
      } catch (error) {
        if (!this.partialFailures.includes(label)) this.partialFailures.push(label)
        console.error(`LayerSentry dashboard ${label} load failed`, error)
      }
    },
    async refresh () {
      if (this.refreshing || this.scopedLoading) return
      this.refreshing = true
      this.fatalError = ''
      this.partialFailures = []
      try {
        await this.loadSites()
        await this.refreshScopedData()
      } catch (error) {
        this.fatalError = this.$t('message.layersentry.platform.dashboard.failed')
        console.error(error)
      } finally {
        this.refreshing = false
      }
    },
    async refreshScopedData () {
      if (this.scopedLoading) return
      this.scopedLoading = true
      this.partialFailures = []
      try {
        await Promise.all([
          this.runSection(this.$t('label.instances'), this.loadInstances),
          this.runSection(this.$t('label.layersentry.kvm.hosts'), this.loadHosts),
          this.runSection(this.$t('label.layersentry.storage.pools'), this.loadStoragePools),
          this.runSection(this.$t('label.network'), this.loadNetworks),
          this.runSection(this.$t('label.layersentry.compute.clusters'), this.loadInfrastructure),
          this.runSection(this.$t('label.layersentry.platform.services'), this.loadPlatformServices),
          this.runSection(this.$t('label.layersentry.capacity'), this.loadCapacity),
          this.runSection(this.$t('label.layersentry.protection.services'), this.loadServiceFacts),
          this.runSection(this.$t('label.layersentry.recent.alerts'), this.loadAlerts),
          this.runSection(this.$t('label.layersentry.recent.activity'), this.loadEvents)
        ])
      } finally {
        this.scopedLoading = false
      }
    },
    async loadSites () {
      if (!this.hasApi('listZones')) return
      this.loadingSites = true
      try {
        const response = await getAPI('listZones', { showicon: true })
        this.sites = response?.listzonesresponse?.zone || []
        if (this.selectedSiteId !== ALL_SITES && !this.sites.some(site => site.id === this.selectedSiteId)) {
          this.selectedSiteId = ALL_SITES
        }
      } finally {
        this.loadingSites = false
      }
    },
    async loadInstances () {
      this.counts.instances = null
      if (!this.hasApi('listVirtualMachines')) return
      const response = await getAPI('listVirtualMachines', {
        ...this.scopedParams(),
        hypervisor: 'KVM',
        listall: true,
        details: 'min',
        page: 1,
        pagesize: 1
      })
      this.counts.instances = responseCount(response, 'listvirtualmachinesresponse', 'virtualmachine')
    },
    async loadHosts () {
      this.counts.hosts = null
      this.counts.hostsUp = null
      this.counts.hostsAlert = null
      if (!this.hasApi('listHosts')) return
      const params = {
        ...this.scopedParams(),
        hypervisor: 'KVM',
        type: 'Routing',
        details: 'min',
        page: 1,
        pagesize: 1
      }
      const [all, up, alert] = await Promise.all([
        getAPI('listHosts', params),
        getAPI('listHosts', { ...params, state: 'Up' }),
        getAPI('listHosts', { ...params, state: 'Alert' })
      ])
      this.counts.hosts = responseCount(all, 'listhostsresponse', 'host')
      this.counts.hostsUp = responseCount(up, 'listhostsresponse', 'host')
      this.counts.hostsAlert = responseCount(alert, 'listhostsresponse', 'host')
    },
    async loadStoragePools () {
      this.counts.storagePools = null
      if (!this.hasApi('listStoragePools')) return
      const response = await getAPI('listStoragePools', {
        ...this.scopedParams(),
        page: 1,
        pagesize: 1
      })
      this.counts.storagePools = responseCount(response, 'liststoragepoolsresponse', 'storagepool')
    },
    async loadNetworks () {
      this.counts.networks = null
      if (!this.hasApi('listNetworks')) return
      const response = await getAPI('listNetworks', {
        ...this.scopedParams(),
        listall: true,
        page: 1,
        pagesize: 1
      })
      this.counts.networks = responseCount(response, 'listnetworksresponse', 'network')
    },
    async loadInfrastructure () {
      this.counts.computeClusters = null
      this.counts.infrastructureGroups = null
      const tasks = []
      if (this.hasApi('listClusters')) {
        tasks.push(getAPI('listClusters', {
          ...this.scopedParams(),
          hypervisor: 'KVM',
          page: 1,
          pagesize: 1
        }).then(response => {
          this.counts.computeClusters = responseCount(response, 'listclustersresponse', 'cluster')
        }))
      }
      if (this.hasApi('listPods')) {
        tasks.push(getAPI('listPods', {
          ...this.scopedParams(),
          page: 1,
          pagesize: 1
        }).then(response => {
          this.counts.infrastructureGroups = responseCount(response, 'listpodsresponse', 'pod')
        }))
      }
      await Promise.all(tasks)
    },
    async loadPlatformServices () {
      this.counts.platformServices = null
      const tasks = []
      let systemVms = 0
      let routers = 0
      if (this.hasApi('listSystemVms')) {
        tasks.push(getAPI('listSystemVms', {
          ...this.scopedParams(),
          page: 1,
          pagesize: 1
        }).then(response => {
          systemVms = responseCount(response, 'listsystemvmsresponse', 'systemvm')
        }))
      }
      if (this.hasApi('listRouters')) {
        tasks.push(getAPI('listRouters', {
          ...this.scopedParams(),
          listall: true,
          page: 1,
          pagesize: 1
        }).then(response => {
          routers = responseCount(response, 'listroutersresponse', 'router')
        }))
      }
      if (tasks.length === 0) return
      await Promise.all(tasks)
      this.counts.platformServices = systemVms + routers
    },
    async loadCapacity () {
      this.capacityMap = {}
      if (!this.hasApi('listCapacity')) return
      this.loadingCapacity = true
      try {
        const response = await getAPI('listCapacity', {
          ...this.scopedParams(),
          fetchlatest: false
        })
        this.capacityMap = aggregateCapacity(response?.listcapacityresponse?.capacity || [])
      } finally {
        this.loadingCapacity = false
      }
    },
    async loadServiceFacts () {
      this.counts.backupOfferings = null
      this.counts.nativeKubernetes = null
      this.counts.buckets = null
      const tasks = []
      if (this.hasApi('listBackupOfferings')) {
        tasks.push(getAPI('listBackupOfferings', {
          ...this.scopedParams(),
          page: 1,
          pagesize: 1
        }).then(response => {
          this.counts.backupOfferings = responseCount(response, 'listbackupofferingsresponse', 'backupoffering')
        }))
      }
      if (this.nativeKubernetesVisible) {
        tasks.push(getAPI('listKubernetesClusters', {
          ...this.scopedParams(),
          listall: true,
          page: 1,
          pagesize: 1
        }).then(response => {
          this.counts.nativeKubernetes = responseCount(response, 'listkubernetesclustersresponse', 'kubernetescluster')
        }))
      }
      if (this.hasApi('listBuckets')) {
        tasks.push(getAPI('listBuckets', {
          ...this.scopedParams(),
          listall: true,
          page: 1,
          pagesize: 1
        }).then(response => {
          this.counts.buckets = responseCount(response, 'listbucketsresponse', 'bucket')
        }))
      }
      await Promise.all(tasks)
    },
    async loadAlerts () {
      this.alerts = []
      this.alertsFailed = false
      if (!this.hasApi('listAlerts')) return
      this.loadingAlerts = true
      try {
        const response = await getAPI('listAlerts', {
          listall: true,
          page: 1,
          pagesize: 6
        })
        this.alerts = response?.listalertsresponse?.alert || []
      } catch (error) {
        this.alertsFailed = true
        throw error
      } finally {
        this.loadingAlerts = false
      }
    },
    async loadEvents () {
      this.events = []
      this.eventsFailed = false
      if (!this.hasApi('listEvents')) return
      this.loadingEvents = true
      try {
        const response = await getAPI('listEvents', {
          listall: true,
          page: 1,
          pagesize: 6
        })
        this.events = response?.listeventsresponse?.event || []
      } catch (error) {
        this.eventsFailed = true
        throw error
      } finally {
        this.loadingEvents = false
      }
    },
    formatCapacityValue (type, value) {
      const numeric = Number(value)
      if (!Number.isFinite(numeric)) return '—'
      if (type === 'CPU_CORE') return numeric.toFixed(0)
      const gib = numeric / (1024 * 1024 * 1024)
      if (gib >= 1024) return `${(gib / 1024).toFixed(2)} TiB`
      return `${gib.toFixed(2)} GiB`
    },
    eventMarkerClass (event) {
      if (event.level === 'ERROR') return 'ls-feed-row__marker--alert'
      if (event.state === 'Completed') return 'ls-feed-row__marker--success'
      return 'ls-feed-row__marker--info'
    }
  }
}
</script>

<style lang="less" scoped>
.ls-platform-dashboard {
  max-width: 1540px;
  margin: 0 auto;
  padding-bottom: 40px;
}

.ls-dashboard-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 16px;
  padding: 18px 20px;
  background: #fff;
  border: 1px solid #e4e7ec;
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);

  &__copy {
    min-width: 0;

    h1 {
      margin: 2px 0 6px;
      color: #101828;
      font-size: 28px;
      line-height: 1.2;
    }

    p {
      max-width: 760px;
      margin: 0;
      color: #667085;
      line-height: 1.55;
    }
  }

  &__actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    flex-wrap: wrap;
  }
}

.ls-eyebrow {
  color: #0f766e;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.ls-site-selector {
  min-width: 210px;
}

.ls-dashboard-alert,
.ls-summary-grid,
.ls-dashboard-row {
  margin-bottom: 16px;
}

.ls-summary-link {
  display: block;
  height: 100%;
  color: inherit;

  &:focus-visible .ls-summary-card {
    outline: 3px solid rgba(15, 118, 110, 0.35);
    outline-offset: 2px;
  }
}

.ls-summary-card,
.ls-dashboard-card {
  height: 100%;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(16, 24, 40, 0.08);
}

.ls-summary-card {
  min-height: 158px;
  transition: box-shadow 0.16s ease, transform 0.16s ease;

  &:hover {
    box-shadow: 0 4px 12px rgba(16, 24, 40, 0.10);
    transform: translateY(-1px);
  }

  &__top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    min-height: 28px;
  }

  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    color: #0f766e;
    background: #f0fdfa;
    border-radius: 8px;
    font-size: 17px;
  }

  &__value {
    margin-top: 18px;
    color: #101828;
    font-size: 28px;
    font-weight: 700;
    line-height: 1;
  }

  &__label {
    margin-top: 7px;
    color: #344054;
    font-weight: 600;
  }

  &__detail {
    margin-top: 4px;
    color: #667085;
    font-size: 12px;
  }
}

.ls-card-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #101828;
  font-weight: 650;
}

.ls-scope-label {
  color: #667085;
  font-size: 12px;
}

.ls-capacity-list {
  display: grid;
  gap: 22px;
}

.ls-capacity-row {
  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 6px;
    color: #475467;
  }
}

.ls-capacity-skeleton,
.ls-inline-empty,
.ls-feed-loading {
  min-height: 168px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #667085;
  text-align: center;
}

.ls-service-list {
  display: grid;
  gap: 4px;
}

.ls-service-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 0;
  border-bottom: 1px solid #f2f4f7;

  &:last-child {
    border-bottom: 0;
  }

  &__hint {
    max-width: 360px;
    margin-top: 3px;
    color: #667085;
    font-size: 12px;
    line-height: 1.45;
  }
}

.ls-feed-card {
  min-height: 350px;
}

.ls-feed-list {
  display: grid;
}

.ls-feed-row {
  display: flex;
  gap: 11px;
  padding: 10px 4px;
  color: inherit;
  border-bottom: 1px solid #f2f4f7;

  &:last-child {
    border-bottom: 0;
  }

  &:hover {
    background: #f9fafb;
  }

  &__marker {
    flex: 0 0 auto;
    width: 8px;
    height: 8px;
    margin-top: 7px;
    border-radius: 50%;

    &--alert { background: #b42318; }
    &--success { background: #15803d; }
    &--info { background: #0f766e; }
  }

  &__content {
    display: grid;
    min-width: 0;
    gap: 2px;

    strong {
      color: #344054;
      overflow-wrap: anywhere;
    }

    small {
      color: #98a2b3;
    }

    > span {
      color: #667085;
      font-size: 12px;
      line-height: 1.4;
      overflow-wrap: anywhere;
    }
  }
}

@media (max-width: 900px) {
  .ls-dashboard-hero {
    flex-direction: column;

    &__actions {
      width: 100%;
      justify-content: flex-start;
    }
  }

  .ls-site-selector {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ls-summary-card {
    transition: none;
  }
}
</style>
