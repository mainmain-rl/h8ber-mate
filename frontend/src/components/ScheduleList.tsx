import React, { useState } from 'react';
import { schedulesAPI } from '../services/api';
import type { Schedule } from '../types';

interface SchedulesByNamespace {
  [namespace: string]: Schedule[];
}

interface ScheduleListProps {
  schedulesByNamespace: SchedulesByNamespace;
  onEdit: (schedule: Schedule) => void;
  onRefresh: () => void;
}

export const ScheduleList: React.FC<ScheduleListProps> = ({
  schedulesByNamespace,
  onEdit,
  onRefresh,
}) => {
  const [error, setError] = useState('');
  const [loadingSchedule, setLoadingSchedule] = useState<number | null>(null);

  const handleToggle = async (schedule: Schedule) => {
    try {
      setLoadingSchedule(schedule.id);
      await schedulesAPI.update(schedule.id, {
        enabled: !schedule.enabled,
      });
      // Refresh data from parent
      onRefresh();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update schedule');
    } finally {
      setLoadingSchedule(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this schedule?')) {
      return;
    }

    try {
      setLoadingSchedule(id);
      await schedulesAPI.delete(id);
      // Refresh data from parent
      onRefresh();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete schedule');
      setLoadingSchedule(null);
    }
  };

  const namespaces = Object.keys(schedulesByNamespace).sort();

  return (
    <>
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4 animate-slideDown">
          {error}
          <button onClick={() => setError('')} className="ml-2 text-red-900 hover:text-red-700">×</button>
        </div>
      )}

      <div className="space-y-6">
        {namespaces.map((namespace) => (
          <div key={namespace} className="bg-white/90 backdrop-blur-sm rounded-xl shadow-soft border border-gray-200/50 overflow-hidden hover:shadow-md transition-all duration-200 animate-fadeIn">
            <div className="px-6 py-4 bg-gradient-to-r from-gray-50 to-blue-50/30 border-b border-gray-200/50">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                  <svg className="w-5 h-5 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                  </svg>
                  <span className="text-gray-600">Namespace:</span> <span className="text-primary-600">{namespace}</span>
                </h3>
                <span className="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-bold bg-gradient-primary text-white shadow-sm">
                  {schedulesByNamespace[namespace].length} schedule{schedulesByNamespace[namespace].length > 1 ? 's' : ''}
                </span>
              </div>
            </div>

            <div className="divide-y divide-gray-200/50">
              {schedulesByNamespace[namespace].map((schedule) => (
                <div key={schedule.id} className="px-6 py-5 hover:bg-gradient-to-r hover:from-gray-50/50 hover:to-transparent transition-all duration-200 group">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-3">
                        <h4 className="text-base font-bold text-gray-900">
                          {schedule.deployment_name}
                        </h4>
                        {schedule.enabled ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-gradient-to-r from-green-400 to-green-500 text-white shadow-sm">
                            ● Enabled
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-600">
                            ○ Disabled
                          </span>
                        )}
                        {schedule.is_scaled_down && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-gradient-to-r from-yellow-400 to-amber-500 text-white shadow-sm animate-pulse-soft">
                            💤 Hibernating
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-6 text-sm">
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-50 border border-red-100">
                          <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                          <span className="font-semibold text-red-600">Down:</span>
                          <span className="font-mono font-bold text-red-700">{schedule.scale_down_time}</span>
                        </div>
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-green-50 border border-green-100">
                          <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                          </svg>
                          <span className="font-semibold text-green-600">Up:</span>
                          <span className="font-mono font-bold text-green-700">{schedule.scale_up_time}</span>
                        </div>
                        {schedule.original_replicas !== null && (
                          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-50 border border-blue-100">
                            <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                            </svg>
                            <span className="font-semibold text-blue-600">Replicas:</span>
                            <span className="font-mono font-bold text-blue-700">{schedule.original_replicas}</span>
                          </div>
                        )}
                      </div>

                      {schedule.last_scaled_at && (
                        <div className="mt-2 text-xs text-gray-500 flex items-center gap-1.5">
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          Last scaled: <span className="font-medium">{new Date(schedule.last_scaled_at).toLocaleString()}</span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2 ml-6 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                      <button
                        onClick={() => onEdit(schedule)}
                        disabled={loadingSchedule === schedule.id}
                        className="inline-flex items-center px-4 py-2 border border-primary-300 text-sm font-semibold rounded-lg text-primary-700 bg-primary-50 hover:bg-primary-100 hover:border-primary-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                        Edit
                      </button>

                      <button
                        onClick={() => handleToggle(schedule)}
                        disabled={loadingSchedule === schedule.id}
                        className={`inline-flex items-center px-4 py-2 border text-sm font-semibold rounded-lg transition-all duration-200 hover:scale-105 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed ${
                          schedule.enabled
                            ? 'border-gray-300 text-gray-700 bg-white hover:bg-gray-50'
                            : 'border-transparent text-white bg-gradient-primary hover:shadow-glow'
                        }`}
                      >
                        {loadingSchedule === schedule.id ? (
                          <svg className="w-4 h-4 mr-1.5 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                        ) : schedule.enabled ? (
                          <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        )}
                        {schedule.enabled ? 'Disable' : 'Enable'}
                      </button>

                      <button
                        onClick={() => handleDelete(schedule.id)}
                        disabled={loadingSchedule === schedule.id}
                        className="inline-flex items-center px-4 py-2 border border-red-300 text-sm font-semibold rounded-lg text-red-700 bg-red-50 hover:bg-red-100 hover:border-red-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  );
};
