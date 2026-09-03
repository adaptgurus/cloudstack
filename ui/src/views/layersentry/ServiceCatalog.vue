<!--
 Licensed to the Apache Software Foundation (ASF) under one
 or more contributor license agreements.  See the NOTICE file
 distributed with this work for additional information
 regarding copyright ownership.  The ASF licenses this file
 to you under the Apache License, Version 2.0 (the
 "License"); you may not use this file except in compliance
 with the License.  You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing,
 software distributed under the License is distributed on an
 "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 KIND, either express or implied.  See the License for the
 specific language governing permissions and limitations
 under the License.
-->

<template>
  <div class="layersentry-service-catalog">
    <div class="catalog-header">
      <div>
        <h1>{{ catalog.title }}</h1>
        <p>{{ catalog.subtitle }}</p>
      </div>
      <a-tag color="blue">Service Catalog</a-tag>
    </div>

    <a-alert
      type="info"
      show-icon
      class="catalog-notice"
      message="Catalog visibility only"
      description="These entries show the services Layersentry can expose through this catalog. Deployment is intentionally disabled until a supported backend service integration is configured." />

    <a-row :gutter="[16, 16]">
      <a-col
        v-for="item in catalog.items"
        :key="item.name"
        :xs="24"
        :md="12"
        :xl="8">
        <a-card class="catalog-card" :bordered="true">
          <div class="catalog-card-title">
            <div class="catalog-card-icon">
              <render-icon :icon="item.icon" />
            </div>
            <div>
              <h3>{{ item.name }}</h3>
              <span>{{ item.category }}</span>
            </div>
          </div>

          <p class="catalog-description">{{ item.description }}</p>

          <div class="catalog-meta">
            <span>Deployment model</span>
            <strong>{{ item.model }}</strong>
          </div>
          <div class="catalog-meta">
            <span>Status</span>
            <a-tag color="orange">Integration required</a-tag>
          </div>

          <a-button block disabled class="catalog-deploy-button">
            Deploy
          </a-button>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script>
const catalogs = {
  dbaas: {
    title: 'DBaaS',
    subtitle: 'Database as a Service deployment catalog',
    items: [
      {
        name: 'PostgreSQL',
        category: 'Relational database',
        icon: 'database-outlined',
        model: 'Managed database service',
        description: 'Catalog entry for PostgreSQL database deployments with infrastructure lifecycle integration.'
      },
      {
        name: 'MySQL / MariaDB',
        category: 'Relational database',
        icon: 'database-outlined',
        model: 'Managed database service',
        description: 'Catalog entry for MySQL-compatible database deployments and associated storage resources.'
      },
      {
        name: 'Redis',
        category: 'In-memory data store',
        icon: 'thunderbolt-outlined',
        model: 'Managed data service',
        description: 'Catalog entry for Redis cache and data-store deployments when a supported provider is connected.'
      },
      {
        name: 'MongoDB',
        category: 'Document database',
        icon: 'cluster-outlined',
        model: 'Managed database service',
        description: 'Catalog entry for document-database deployments through a supported automation integration.'
      }
    ]
  },
  apaas: {
    title: 'APaaS',
    subtitle: 'Application Platform as a Service deployment catalog',
    items: [
      {
        name: 'Container Application',
        category: 'Container runtime',
        icon: 'container-outlined',
        model: 'Application service',
        description: 'Catalog entry for containerized application deployments backed by a configured application platform.'
      },
      {
        name: 'Java Runtime',
        category: 'Application runtime',
        icon: 'code-outlined',
        model: 'Application service',
        description: 'Catalog entry for Java application runtime deployments with platform lifecycle automation.'
      },
      {
        name: 'Node.js Runtime',
        category: 'Application runtime',
        icon: 'code-outlined',
        model: 'Application service',
        description: 'Catalog entry for Node.js workloads when an application deployment backend is configured.'
      },
      {
        name: 'Python Runtime',
        category: 'Application runtime',
        icon: 'code-outlined',
        model: 'Application service',
        description: 'Catalog entry for Python application runtimes exposed through a supported platform integration.'
      }
    ]
  }
}

export default {
  name: 'LayersentryServiceCatalog',
  computed: {
    catalog () {
      return catalogs[this.$route.name] || catalogs.dbaas
    }
  }
}
</script>

<style lang="less" scoped>
.layersentry-service-catalog {
  padding: 20px 24px 32px;
}

.catalog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.catalog-header h1 {
  margin: 0 0 4px;
  font-size: 24px;
  line-height: 1.3;
}

.catalog-header p {
  margin: 0;
  color: rgba(0, 0, 0, 0.45);
}

.catalog-notice {
  margin-bottom: 18px;
}

.catalog-card {
  height: 100%;
}

.catalog-card-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.catalog-card-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  border-radius: 8px;
  background: rgba(24, 73, 181, 0.08);
  color: #1849b5;
  font-size: 20px;
}

.catalog-card-title h3 {
  margin: 0 0 2px;
  font-size: 16px;
}

.catalog-card-title span,
.catalog-description,
.catalog-meta span {
  color: rgba(0, 0, 0, 0.45);
}

.catalog-description {
  min-height: 66px;
  margin-bottom: 18px;
  line-height: 1.55;
}

.catalog-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 0;
  border-top: 1px solid #f0f0f0;
}

.catalog-meta strong {
  text-align: right;
  font-weight: 500;
}

.catalog-deploy-button {
  margin-top: 14px;
}

@media (max-width: 768px) {
  .layersentry-service-catalog {
    padding: 16px;
  }

  .catalog-header {
    flex-direction: column;
  }

  .catalog-description {
    min-height: 0;
  }
}
</style>
