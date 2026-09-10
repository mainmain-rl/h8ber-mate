import React, { useState, useEffect } from 'react';
import { Layout } from '../components/Layout';
import { schedulesAPI } from '../services/api';
import type { Schedule } from '../types';
import { ScheduleList } from '../components/ScheduleList';
import { ScheduleForm } from '../components/ScheduleForm';

interface SchedulesByNamespace {
  [namespace: string]: Schedule[];
}

const NAMESPACE_COLORS = [
  'bg-blue-500',
  'bg-purple-500',
  'bg-pink-500',
  'bg-indigo-500',
  'bg-cyan-500',
  'bg-teal-500',
  'bg-green-500',
  'bg-lime-500',
  'bg-amber-500',
  'bg-orange-500',
];

export const DashboardPage: React.FC = () => {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);
  const [selectedNamespaces, setSelectedNamespaces] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const schedulesData = await schedulesAPI.getAll();

      setSchedules(schedulesData);

      // Initialize all namespaces as selected
      const allNamespaces = new Set(schedulesData.map(s => s.namespace));
      setSelectedNamespaces(allNamespaces);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleScheduleCreated = () => {
    setShowForm(false);
    setEditingSchedule(null);
    loadData();
  };

  const handleEditSchedule = (schedule: Schedule) => {
    setEditingSchedule(schedule);
    setShowForm(true);
  };

  const handleCancelForm = () => {
    setShowForm(false);
    setEditingSchedule(null);
  };

  const toggleNamespace = (namespace: string) => {
    const newSelected = new Set(selectedNamespaces);
    if (newSelected.has(namespace)) {
      newSelected.delete(namespace);
    } else {
      newSelected.add(namespace);
    }
    setSelectedNamespaces(newSelected);
  };

  const toggleAllNamespaces = () => {
    const allNamespaces = new Set(schedules.map(s => s.namespace));

    if (selectedNamespaces.size === allNamespaces.size) {
      // Deselect all
      setSelectedNamespaces(new Set());
    } else {
      // Select all
      setSelectedNamespaces(allNamespaces);
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin"></div>
            <span className="text-gray-600 font-medium">Loading...</span>
          </div>
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout>
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl shadow-soft">
          {error}
        </div>
      </Layout>
    );
  }

  // Filter schedules by namespace
  const filteredSchedules = schedules.filter(schedule =>
    selectedNamespaces.has(schedule.namespace)
  );

  // Group schedules by namespace
  const schedulesByNamespace: SchedulesByNamespace = filteredSchedules.reduce((acc, schedule) => {
    if (!acc[schedule.namespace]) {
      acc[schedule.namespace] = [];
    }
    acc[schedule.namespace].push(schedule);
    return acc;
  }, {} as SchedulesByNamespace);

  // Get namespaces with schedules
  const namespacesWithSchedules = Array.from(
    new Set(schedules.map(s => s.namespace))
  ).sort();

  const getNamespaceColor = (index: number) => {
    return NAMESPACE_COLORS[index % NAMESPACE_COLORS.length];
  };

  return (
    <Layout>
      <div className="flex gap-6 h-full animate-fadeIn relative">
        {/* Sidebar - Namespace Filters */}
        <div className="w-72 flex-shrink-0 space-y-4">
          {/* Namespace Filters */}
          {namespacesWithSchedules.length > 0 && (
            <div className="bg-white/90 backdrop-blur-sm rounded-xl shadow-soft border border-gray-200/50 p-5 hover:shadow-md transition-all duration-200 animate-slideDown">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-gray-800 uppercase tracking-wide flex items-center gap-2">
                  <svg className="w-4 h-4 text-accent-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                  </svg>
                  Namespaces
                </h3>
                <button
                  onClick={toggleAllNamespaces}
                  className="text-xs font-semibold text-primary-600 hover:text-primary-700 transition-colors"
                >
                  {selectedNamespaces.size === namespacesWithSchedules.length ? 'None' : 'All'}
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {namespacesWithSchedules.map((namespace, index) => {
                  const isSelected = selectedNamespaces.has(namespace);
                  const count = schedules.filter(s => s.namespace === namespace).length;

                  return (
                    <button
                      key={namespace}
                      onClick={() => toggleNamespace(namespace)}
                      className={`group relative px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 ${
                        isSelected
                          ? `${getNamespaceColor(index)} text-white shadow-md scale-105`
                          : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                      }`}
                    >
                      <span className="flex items-center gap-1.5">
                        {namespace}
                        <span className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold ${
                          isSelected ? 'bg-white/20' : 'bg-gray-200'
                        }`}>
                          {count}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Main Content */}
        <div className="flex-1 space-y-6 relative">
          <div className="flex justify-between items-center animate-slideDown">
            <div>
              <h2 className="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 bg-clip-text text-transparent">
                Deployment Schedules
              </h2>
              <p className="text-sm text-gray-600 mt-2 flex items-center gap-2">
                <span className="inline-block w-2 h-2 rounded-full bg-green-500 animate-pulse-soft"></span>
                <span className="text-gray-500">
                  {filteredSchedules.length} schedule{filteredSchedules.length !== 1 ? 's' : ''}
                </span>
              </p>
            </div>
            <button
              onClick={() => setShowForm(true)}
              className="inline-flex items-center gap-2 px-5 py-2.5 border border-transparent shadow-soft text-sm font-semibold rounded-lg text-white bg-gradient-primary hover:shadow-glow focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 transition-all duration-200 hover:scale-105"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Create Schedule
            </button>
          </div>

          {filteredSchedules.length === 0 ? (
            <div className="bg-white/90 backdrop-blur-sm rounded-xl shadow-soft border border-gray-200/50 p-12 text-center animate-fadeIn">
              <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">No schedules found</h3>
              <p className="text-gray-500 mb-4">
                {namespacesWithSchedules.length === 0
                  ? 'Create your first schedule to get started'
                  : 'Try selecting different namespace filters'}
              </p>
            </div>
          ) : (
            <div className="animate-slideUp">
              <ScheduleList
                schedulesByNamespace={schedulesByNamespace}
                onEdit={handleEditSchedule}
                onRefresh={loadData}
              />
            </div>
          )}
        </div>

        {/* Modal Popup - Create/Edit Schedule */}
        {showForm && (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 bg-black/60 backdrop-blur-md z-40 animate-fadeIn flex items-center justify-center p-4"
              onClick={handleCancelForm}
            >
              {/* Modal */}
              <div
                className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden animate-popIn"
                onClick={(e) => e.stopPropagation()}
              >
                {/* Header */}
                <div className="bg-gradient-to-r from-primary-500 via-primary-600 to-purple-600 px-8 py-6 relative overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-br from-white/10 to-transparent"></div>
                  <div className="relative flex items-start justify-between">
                    <div>
                      <h2 className="text-2xl font-bold text-white flex items-center gap-3 mb-2">
                        <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
                          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                          </svg>
                        </div>
                        {editingSchedule ? 'Edit Schedule' : 'Create New Schedule'}
                      </h2>
                      <p className="text-primary-50 text-sm pl-13">
                        {editingSchedule
                          ? `Editing ${editingSchedule.deployment_name} in ${editingSchedule.namespace}`
                          : 'Configure a new hibernation schedule for your deployment'}
                      </p>
                    </div>
                    <button
                      onClick={handleCancelForm}
                      className="text-white hover:bg-white/20 rounded-xl p-2.5 transition-all duration-200 hover:scale-110"
                    >
                      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>

                {/* Form Content */}
                <div className="p-8 overflow-y-auto max-h-[calc(90vh-120px)]">
                  <ScheduleForm
                    existingSchedule={editingSchedule || undefined}
                    onSuccess={handleScheduleCreated}
                    onCancel={handleCancelForm}
                  />
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      <style>{`
        @keyframes popIn {
          0% {
            transform: scale(0.8);
            opacity: 0;
          }
          100% {
            transform: scale(1);
            opacity: 1;
          }
        }
        .animate-popIn {
          animation: popIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
      `}</style>
    </Layout>
  );
};
