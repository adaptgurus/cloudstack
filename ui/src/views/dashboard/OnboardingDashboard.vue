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
  <div class="onboarding">
    <div class="hero">
      <img class="brand-logo" src="assets/layersentry-logo.svg" alt="Layersentry">
      <div class="release-badge">V1.0</div>
      <h1>Secure cloud infrastructure management</h1>
      <p class="hero-copy">
        Layersentry provides one operational plane for compute, storage, networking,
        images, projects, identity, infrastructure, Kubernetes and backup services.
      </p>
    </div>

    <div class="capabilities">
      <div class="capability-card">
        <div class="capability-kicker">INFRASTRUCTURE</div>
        <h3>Unified operations</h3>
        <p>Manage virtual infrastructure, resource profiles and cloud resources from one console.</p>
      </div>
      <div class="capability-card">
        <div class="capability-kicker">SECURITY</div>
        <h3>Controlled administration</h3>
        <p>Use projects, accounts, domains, roles and platform controls to govern administrative access.</p>
      </div>
      <div class="capability-card">
        <div class="capability-kicker">SERVICES</div>
        <h3>Private-cloud services</h3>
        <p>Use Kubernetes, object storage buckets and backup services when their required providers are configured.</p>
      </div>
    </div>

    <div class="setup-panel">
      <div>
        <div class="setup-title">Complete infrastructure setup</div>
        <div class="setup-copy">
          Change the initial administrator password, then create the first datacenter or edge site.
        </div>
      </div>
      <a-button @click="() => { step = 1 }" type="primary" size="large">
        Continue with installation
        <double-right-outlined />
      </a-button>
    </div>

    <a-modal
      :title="$t('message.change.password')"
      :visible="step === 1"
      :closable="true"
      :maskClosable="false"
      :footer="null"
      @cancel="closeAction"
      centered
      width="auto">
      <change-user-password
        :resource="resource"
        @close-action="() => { if (step !== 2) step = 0 }"
        @refresh-data="() => { step = 2 }" />
    </a-modal>
    <a-modal
      title="Create infrastructure site"
      :visible="step === 2"
      :closable="true"
      :maskClosable="false"
      :footer="null"
      @cancel="closeAction"
      centered
      width="auto">
      <zone-wizard
        @close-action="closeAction"
        @refresh-data="parentFetchData" />
    </a-modal>
  </div>
</template>

<script>
import ChangeUserPassword from '@/views/iam/ChangeUserPassword.vue'
import ZoneWizard from '@/views/infra/zone/ZoneWizard.vue'

export default {
  name: 'OnboardingDashboard',
  components: {
    ChangeUserPassword,
    ZoneWizard
  },
  inject: ['parentFetchData'],
  data () {
    return {
      step: 0,
      resource: {
        id: this.$store.getters.userInfo.id,
        username: this.$store.getters.userInfo.username
      }
    }
  },
  methods: {
    closeAction () {
      this.step = 0
    }
  }
}
</script>

<style scoped lang="scss">
.onboarding {
  min-height: calc(100vh - 170px);
  padding: 42px;
  background:
    radial-gradient(circle at 85% 0%, rgba(15, 118, 110, 0.10), transparent 34%),
    linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(16, 24, 40, 0.08);
}

.hero {
  max-width: 920px;
  margin: 0 auto;
  text-align: center;
}

.brand-logo {
  width: 280px;
  max-width: 78vw;
  height: auto;
  margin-bottom: 10px;
}

.release-badge {
  display: inline-block;
  margin: 0 0 18px;
  padding: 5px 12px;
  color: #0f766e;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

h1 {
  margin: 0;
  color: #101828;
  font-size: 34px;
  line-height: 1.2;
  font-weight: 700;
}

.hero-copy {
  max-width: 760px;
  margin: 18px auto 0;
  color: #667085;
  font-size: 16px;
  line-height: 1.7;
}

.capabilities {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
  max-width: 1100px;
  margin: 42px auto 0;
}

.capability-card {
  min-height: 170px;
  padding: 24px;
  background: #ffffff;
  border: 1px solid #e4e7ec;
  border-radius: 10px;
  box-shadow: 0 4px 14px rgba(16, 24, 40, 0.05);
}

.capability-kicker {
  margin-bottom: 12px;
  color: #0f766e;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.capability-card h3 {
  margin: 0 0 10px;
  color: #1f2933;
  font-size: 18px;
}

.capability-card p {
  margin: 0;
  color: #667085;
  line-height: 1.6;
}

.setup-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  max-width: 1100px;
  margin: 24px auto 0;
  padding: 24px 26px;
  background: #1f2933;
  border-radius: 10px;
}

.setup-title {
  margin-bottom: 5px;
  color: #ffffff;
  font-size: 17px;
  font-weight: 700;
}

.setup-copy {
  color: rgba(255, 255, 255, 0.72);
  line-height: 1.5;
}

.setup-panel :deep(.ant-btn-primary) {
  flex: 0 0 auto;
  background: #0f766e;
  border-color: #0f766e;
}

@media (max-width: 900px) {
  .onboarding {
    padding: 28px 18px;
  }

  .capabilities {
    grid-template-columns: 1fr;
  }

  .setup-panel {
    align-items: stretch;
    flex-direction: column;
  }

  h1 {
    font-size: 28px;
  }
}
</style>
