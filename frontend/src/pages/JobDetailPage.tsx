import React from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Play, Pause, Square, Download } from 'lucide-react'
import { Link } from 'react-router-dom'

import { jobsApi } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { formatDate, formatDuration, getJobStatusColor, getJobStatusIcon, formatNumber } from '@/lib/utils'

export const JobDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()

  const { data: job, isLoading } = useQuery({
    queryKey: ['jobs', id],
    queryFn: () => jobsApi.getJob(id!),
    enabled: !!id,
  })

  const { data: events, isLoading: eventsLoading } = useQuery({
    queryKey: ['jobs', id, 'events'],
    queryFn: () => jobsApi.getJobEvents(id!),
    enabled: !!id,
  })

  const { data: results, isLoading: resultsLoading } = useQuery({
    queryKey: ['jobs', id, 'results'],
    queryFn: () => jobsApi.getJobResults(id!),
    enabled: !!id,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!job) {
    return <div>Job not found</div>
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/jobs">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Jobs
            </Link>
          </Button>
          <div>
            <h1 className="text-3xl font-bold">{job.name}</h1>
            <p className="text-muted-foreground flex items-center space-x-2">
              <span className="text-lg">{getJobStatusIcon(job.status)}</span>
              <span className={getJobStatusColor(job.status)}>
                {job.status.toUpperCase()}
              </span>
            </p>
          </div>
        </div>

        {/* Job Controls */}
        <div className="flex items-center space-x-2">
          {job.status === 'running' && (
            <Button variant="outline">
              <Pause className="w-4 h-4 mr-2" />
              Pause
            </Button>
          )}
          {job.status === 'paused' && (
            <Button variant="outline">
              <Play className="w-4 h-4 mr-2" />
              Resume
            </Button>
          )}
          {(job.status === 'running' || job.status === 'paused') && (
            <Button variant="destructive">
              <Square className="w-4 h-4 mr-2" />
              Cancel
            </Button>
          )}
          {results && results.length > 0 && (
            <Button>
              <Download className="w-4 h-4 mr-2" />
              Export Results
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Job Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Overview */}
          <Card>
            <CardHeader>
              <CardTitle>Job Overview</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Hash Type</p>
                  <p className="font-medium">{job.hash_type || 'Auto-detected'}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Profile</p>
                  <p className="font-medium">{job.profile_name || 'Default'}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Total Hashes</p>
                  <p className="font-medium">
                    {job.total_hashes ? formatNumber(job.total_hashes) : 'Unknown'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Cracked</p>
                  <p className="font-medium text-success">
                    {formatNumber(job.cracked_count)}
                    {job.progress_percentage > 0 && ` (${job.progress_percentage}%)`}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Started</p>
                  <p className="font-medium">
                    {job.started_at ? formatDate(job.started_at) : 'Not started'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Runtime</p>
                  <p className="font-medium">
                    {job.runtime_seconds ? formatDuration(job.runtime_seconds) : 'N/A'}
                  </p>
                </div>
              </div>

              {/* Progress Bar */}
              {job.progress_percentage > 0 && (
                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <span>Progress</span>
                    <span>{job.progress_percentage}%</span>
                  </div>
                  <div className="w-full bg-secondary rounded-full h-3">
                    <div 
                      className="bg-primary h-3 rounded-full transition-all"
                      style={{ width: `${job.progress_percentage}%` }}
                    />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent Events */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Events</CardTitle>
              <CardDescription>Latest activity for this job</CardDescription>
            </CardHeader>
            <CardContent>
              {eventsLoading ? (
                <LoadingSpinner />
              ) : events && events.length > 0 ? (
                <div className="space-y-3 max-h-64 overflow-y-auto">
                  {events.slice(0, 10).map((event) => (
                    <div key={event.id} className="flex items-start space-x-3 p-3 border rounded-lg">
                      <div className="text-sm">
                        <p className="font-medium">{event.event_type.replace('_', ' ').toUpperCase()}</p>
                        <p className="text-muted-foreground">{event.message}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {formatDate(event.created_at)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-4">No events recorded</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Quick Stats */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Quick Stats</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-success">
                  {formatNumber(job.cracked_count)}
                </div>
                <p className="text-sm text-muted-foreground">Hashes Cracked</p>
              </div>
              
              {job.progress_percentage > 0 && (
                <div className="text-center">
                  <div className="text-2xl font-bold">
                    {job.progress_percentage}%
                  </div>
                  <p className="text-sm text-muted-foreground">Complete</p>
                </div>
              )}
              
              {job.runtime_seconds && (
                <div className="text-center">
                  <div className="text-2xl font-bold">
                    {formatDuration(job.runtime_seconds)}
                  </div>
                  <p className="text-sm text-muted-foreground">Runtime</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Cracked Results Preview */}
          {results && results.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Recent Cracks</CardTitle>
                <CardDescription>Latest cracked hashes</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {results.slice(0, 5).map((result) => (
                    <div key={result.id} className="text-sm">
                      <p className="font-mono text-xs truncate">
                        {result.hash_value}
                      </p>
                      <p className="text-muted-foreground truncate">
                        {result.plaintext}
                      </p>
                    </div>
                  ))}
                </div>
                {results.length > 5 && (
                  <p className="text-xs text-muted-foreground mt-2">
                    +{results.length - 5} more results
                  </p>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}