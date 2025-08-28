import React from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  Clock,
  CheckCircle,
  AlertCircle,
  Zap,
  Database,
  Server,
  HardDrive,
  Users,
  TrendingUp,
} from 'lucide-react'

import { systemApi, jobsApi } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { formatNumber, formatDuration, getJobStatusColor, getJobStatusIcon } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import type { Job, SystemHealth } from '@/types/api'

export const DashboardPage: React.FC = () => {
  const { user } = useAuth()

  const { data: systemHealth, isLoading: healthLoading } = useQuery({
    queryKey: ['system', 'health'],
    queryFn: systemApi.getHealth,
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  const { data: recentJobs, isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs', 'recent'],
    queryFn: () => jobsApi.getJobs({ page: 1, size: 10 }),
  })

  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['system', 'metrics'],
    queryFn: () => systemApi.getMetrics({
      metric_type: 'performance',
      start_time: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    }),
    refetchInterval: 60000, // Refresh every minute
  })

  if (healthLoading && jobsLoading && metricsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const getHealthStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-success'
      case 'degraded':
        return 'text-warning'
      case 'unhealthy':
        return 'text-destructive'
      default:
        return 'text-muted-foreground'
    }
  }

  const getServiceStatusIcon = (status: string) => {
    return status === 'up' ? (
      <CheckCircle className="w-4 h-4 text-success" />
    ) : (
      <AlertCircle className="w-4 h-4 text-destructive" />
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome back, {user?.email}. Here's an overview of your system status.
        </p>
      </div>

      {/* System Health Status */}
      {systemHealth && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Activity className="w-5 h-5" />
              <span>System Health</span>
              <span className={getHealthStatusColor(systemHealth.status)}>
                ({systemHealth.status.toUpperCase()})
              </span>
            </CardTitle>
            <CardDescription>
              Current status of all system components
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="flex items-center space-x-2">
                {getServiceStatusIcon(systemHealth.services.database)}
                <span className="text-sm">Database</span>
              </div>
              <div className="flex items-center space-x-2">
                {getServiceStatusIcon(systemHealth.services.queue)}
                <span className="text-sm">Queue</span>
              </div>
              <div className="flex items-center space-x-2">
                {getServiceStatusIcon(systemHealth.services.worker)}
                <span className="text-sm">Worker</span>
              </div>
              <div className="flex items-center space-x-2">
                {getServiceStatusIcon(systemHealth.services.storage)}
                <span className="text-sm">Storage</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Key Metrics */}
      {systemHealth && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Jobs</CardTitle>
              <Zap className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-info">
                {systemHealth.metrics.active_jobs}
              </div>
              <p className="text-xs text-muted-foreground">
                Currently running
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Queue Size</CardTitle>
              <Clock className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-warning">
                {systemHealth.metrics.queued_jobs}
              </div>
              <p className="text-xs text-muted-foreground">
                Pending execution
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Cracked</CardTitle>
              <CheckCircle className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-success">
                {formatNumber(systemHealth.metrics.total_hashes_cracked)}
              </div>
              <p className="text-xs text-muted-foreground">
                All time
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg Crack Time</CardTitle>
              <TrendingUp className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatDuration(systemHealth.metrics.avg_crack_time)}
              </div>
              <p className="text-xs text-muted-foreground">
                Per hash
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Recent Jobs */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Jobs</CardTitle>
          <CardDescription>
            Latest job activity and status updates
          </CardDescription>
        </CardHeader>
        <CardContent>
          {jobsLoading ? (
            <div className="flex items-center justify-center h-32">
              <LoadingSpinner />
            </div>
          ) : recentJobs?.items.length ? (
            <div className="space-y-4">
              {recentJobs.items.slice(0, 5).map((job: Job) => (
                <div
                  key={job.id}
                  className="flex items-center justify-between p-4 border rounded-lg"
                >
                  <div className="flex items-center space-x-3">
                    <span className="text-lg">
                      {getJobStatusIcon(job.status)}
                    </span>
                    <div>
                      <h4 className="font-medium">{job.name}</h4>
                      <p className="text-sm text-muted-foreground">
                        {job.hash_type && `${job.hash_type} • `}
                        {job.total_hashes 
                          ? `${job.cracked_count.toLocaleString()} / ${job.total_hashes.toLocaleString()} cracked`
                          : `${job.cracked_count.toLocaleString()} cracked`
                        }
                      </p>
                    </div>
                  </div>
                  
                  <div className="text-right">
                    <span className={`text-sm font-medium ${getJobStatusColor(job.status)}`}>
                      {job.status.toUpperCase()}
                    </span>
                    {job.progress_percentage > 0 && (
                      <p className="text-xs text-muted-foreground">
                        {job.progress_percentage}% complete
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-muted-foreground py-8">
              No jobs found. Create your first job by uploading hash files.
            </div>
          )}
        </CardContent>
      </Card>

      {/* System Resources (if metrics available) */}
      {metrics && metrics.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">CPU Usage</CardTitle>
              <Server className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {metrics.find(m => m.metric_name === 'cpu_usage')?.value || 0}%
              </div>
              <div className="w-full bg-secondary rounded-full h-2 mt-2">
                <div 
                  className="bg-primary h-2 rounded-full transition-all"
                  style={{
                    width: `${Math.min(metrics.find(m => m.metric_name === 'cpu_usage')?.value || 0, 100)}%`
                  }}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Memory Usage</CardTitle>
              <Database className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {metrics.find(m => m.metric_name === 'memory_usage')?.value || 0}%
              </div>
              <div className="w-full bg-secondary rounded-full h-2 mt-2">
                <div 
                  className="bg-primary h-2 rounded-full transition-all"
                  style={{
                    width: `${Math.min(metrics.find(m => m.metric_name === 'memory_usage')?.value || 0, 100)}%`
                  }}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Disk Usage</CardTitle>
              <HardDrive className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {metrics.find(m => m.metric_name === 'disk_usage')?.value || 0}%
              </div>
              <div className="w-full bg-secondary rounded-full h-2 mt-2">
                <div 
                  className="bg-primary h-2 rounded-full transition-all"
                  style={{
                    width: `${Math.min(metrics.find(m => m.metric_name === 'disk_usage')?.value || 0, 100)}%`
                  }}
                />
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}