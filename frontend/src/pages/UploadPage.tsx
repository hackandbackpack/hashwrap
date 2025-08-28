import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Upload, FileText, Trash2, Plus } from 'lucide-react'
import { useDropzone } from 'react-dropzone'

import { projectsApi, uploadsApi } from '@/lib/api-client'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { formatFileSize, formatDate, cn } from '@/lib/utils'
import type { Project, Upload as UploadType } from '@/types/api'

const uploadSchema = z.object({
  project_id: z.string().min(1, 'Please select a project'),
  hash_type_override: z.string().optional(),
})

type UploadForm = z.infer<typeof uploadSchema>

const createProjectSchema = z.object({
  name: z.string().min(1, 'Project name is required'),
  description: z.string().optional(),
})

type CreateProjectForm = z.infer<typeof createProjectSchema>

export const UploadPage: React.FC = () => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [showCreateProject, setShowCreateProject] = useState(false)
  const queryClient = useQueryClient()

  const { data: projects, isLoading: projectsLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.getProjects,
  })

  const { data: uploads, isLoading: uploadsLoading } = useQuery({
    queryKey: ['uploads'],
    queryFn: () => uploadsApi.getUploads(),
  })

  const uploadMutation = useMutation({
    mutationFn: uploadsApi.createUpload,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['uploads'] })
      setSelectedFiles([])
      uploadForm.reset()
    },
  })

  const createProjectMutation = useMutation({
    mutationFn: projectsApi.createProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setShowCreateProject(false)
      projectForm.reset()
    },
  })

  const deleteUploadMutation = useMutation({
    mutationFn: uploadsApi.deleteUpload,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['uploads'] })
    },
  })

  const uploadForm = useForm<UploadForm>({
    resolver: zodResolver(uploadSchema),
    defaultValues: {
      project_id: '',
      hash_type_override: '',
    },
  })

  const projectForm = useForm<CreateProjectForm>({
    resolver: zodResolver(createProjectSchema),
    defaultValues: {
      name: '',
      description: '',
    },
  })

  const onDrop = (acceptedFiles: File[]) => {
    setSelectedFiles(prev => [...prev, ...acceptedFiles])
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/plain': ['.txt'],
      'text/csv': ['.csv'],
    },
    maxSize: 100 * 1024 * 1024, // 100MB
  })

  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handleUpload = async (data: UploadForm) => {
    if (selectedFiles.length === 0) return

    for (const file of selectedFiles) {
      await uploadMutation.mutateAsync({
        file,
        project_id: data.project_id,
        hash_type_override: data.hash_type_override || undefined,
      })
    }
  }

  const handleCreateProject = async (data: CreateProjectForm) => {
    await createProjectMutation.mutateAsync(data)
  }

  const handleDeleteUpload = async (id: string) => {
    if (confirm('Are you sure you want to delete this upload?')) {
      await deleteUploadMutation.mutateAsync(id)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Upload Hash Files</h1>
        <p className="text-muted-foreground">
          Upload hash files to start new cracking jobs. Supported formats: TXT, CSV
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload Form */}
        <div className="space-y-6">
          {/* Project Selection */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Select Project</CardTitle>
                  <CardDescription>
                    Choose a project or create a new one
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowCreateProject(true)}
                >
                  <Plus className="w-4 h-4 mr-2" />
                  New Project
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {projectsLoading ? (
                <LoadingSpinner />
              ) : (
                <div>
                  <Label htmlFor="project" required>Project</Label>
                  <select
                    id="project"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    {...uploadForm.register('project_id')}
                  >
                    <option value="">Select a project...</option>
                    {projects?.map((project: Project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                  {uploadForm.formState.errors.project_id && (
                    <p className="text-sm text-destructive mt-1">
                      {uploadForm.formState.errors.project_id.message}
                    </p>
                  )}
                </div>
              )}

              {/* Create Project Form */}
              {showCreateProject && (
                <div className="mt-4 p-4 border rounded-lg bg-muted/50">
                  <form onSubmit={projectForm.handleSubmit(handleCreateProject)} className="space-y-4">
                    <div>
                      <Label htmlFor="project-name" required>Project Name</Label>
                      <Input
                        id="project-name"
                        placeholder="Enter project name"
                        {...projectForm.register('name')}
                        error={projectForm.formState.errors.name?.message}
                      />
                    </div>
                    
                    <div>
                      <Label htmlFor="project-description">Description</Label>
                      <Input
                        id="project-description"
                        placeholder="Optional description"
                        {...projectForm.register('description')}
                      />
                    </div>

                    <div className="flex space-x-2">
                      <Button
                        type="submit"
                        size="sm"
                        loading={createProjectMutation.isPending}
                      >
                        Create Project
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setShowCreateProject(false)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </form>
                </div>
              )}
            </CardContent>
          </Card>

          {/* File Upload */}
          <Card>
            <CardHeader>
              <CardTitle>Upload Files</CardTitle>
              <CardDescription>
                Drop files here or click to browse
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div
                {...getRootProps()}
                className={cn(
                  'border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors',
                  isDragActive
                    ? 'border-primary bg-primary/5'
                    : 'border-muted-foreground/25 hover:border-primary/50'
                )}
              >
                <input {...getInputProps()} />
                <Upload className="w-8 h-8 mx-auto mb-4 text-muted-foreground" />
                {isDragActive ? (
                  <p>Drop the files here...</p>
                ) : (
                  <div>
                    <p>Drag and drop files here, or click to select</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      Supports: .txt, .csv (max 100MB per file)
                    </p>
                  </div>
                )}
              </div>

              {/* Selected Files */}
              {selectedFiles.length > 0 && (
                <div className="mt-4 space-y-2">
                  <Label>Selected Files ({selectedFiles.length})</Label>
                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {selectedFiles.map((file, index) => (
                      <div
                        key={index}
                        className="flex items-center justify-between p-2 bg-muted rounded-md"
                      >
                        <div className="flex items-center space-x-2">
                          <FileText className="w-4 h-4" />
                          <span className="text-sm truncate">{file.name}</span>
                          <span className="text-xs text-muted-foreground">
                            ({formatFileSize(file.size)})
                          </span>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeFile(index)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Hash Type Override */}
              <div className="mt-4">
                <Label htmlFor="hash-type">Hash Type Override (Optional)</Label>
                <Input
                  id="hash-type"
                  placeholder="e.g., MD5, SHA1, NTLM"
                  {...uploadForm.register('hash_type_override')}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Leave empty for automatic detection
                </p>
              </div>

              <Button
                onClick={uploadForm.handleSubmit(handleUpload)}
                className="w-full mt-4"
                disabled={selectedFiles.length === 0 || !uploadForm.watch('project_id')}
                loading={uploadMutation.isPending}
              >
                Upload Files
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Recent Uploads */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Uploads</CardTitle>
            <CardDescription>
              Your recently uploaded hash files
            </CardDescription>
          </CardHeader>
          <CardContent>
            {uploadsLoading ? (
              <LoadingSpinner />
            ) : uploads?.length ? (
              <div className="space-y-3">
                {uploads.slice(0, 10).map((upload: UploadType) => (
                  <div
                    key={upload.id}
                    className="flex items-center justify-between p-3 border rounded-lg"
                  >
                    <div>
                      <h4 className="font-medium text-sm">{upload.original_filename}</h4>
                      <p className="text-xs text-muted-foreground">
                        {formatFileSize(upload.file_size)} • {formatDate(upload.created_at)}
                        {upload.hash_count && ` • ${upload.hash_count.toLocaleString()} hashes`}
                      </p>
                      {upload.detected_hash_types.length > 0 && (
                        <p className="text-xs text-muted-foreground">
                          Types: {upload.detected_hash_types.join(', ')}
                        </p>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteUpload(upload.id)}
                      loading={deleteUploadMutation.isPending}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center text-muted-foreground py-8">
                No uploads yet. Upload your first hash file to get started.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}