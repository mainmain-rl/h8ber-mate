import React, { useState, useEffect } from 'react';
import { k8sAPI, schedulesAPI } from '../services/api';
import type { DeploymentInfo, Schedule } from '../types';

interface ScheduleFormProps {
  existingSchedule?: Schedule;
  onSuccess: () => void;
  onCancel: () => void;
}

export const ScheduleForm: React.FC<ScheduleFormProps> = ({
  existingSchedule,
  onSuccess,
  onCancel,
}) => {
  const [namespaces, setNamespaces] = useState<string[]>([]);
  const [deployments, setDeployments] = useState<DeploymentInfo[]>([]);
  const [selectedNamespace, setSelectedNamespace] = useState(existingSchedule?.namespace || '');
  const [selectedDeployment, setSelectedDeployment] = useState(existingSchedule?.deployment_name || '');
  const [scaleDownTime, setScaleDownTime] = useState(existingSchedule?.scale_down_time || '19:00');
  const [scaleUpTime, setScaleUpTime] = useState(existingSchedule?.scale_up_time || '08:00');
  const [enabled, setEnabled] = useState(existingSchedule?.enabled ?? true);
  const [loading, setLoading] = useState(false);
  const [loadingDeployments, setLoadingDeployments] = useState(false);
  const [error, setError] = useState('');
  const [existingScheduleForDeployment, setExistingScheduleForDeployment] = useState<Schedule | null>(null);

  const isEditMode = !!existingSchedule;

  useEffect(() => {
    loadNamespaces();
  }, []);

  useEffect(() => {
    if (selectedNamespace) {
      loadDeployments();
    } else {
      setDeployments([]);
      setSelectedDeployment('');
    }
  }, [selectedNamespace]);

  useEffect(() => {
    // Only check for duplicates in create mode when deployment is selected
    if (!isEditMode && selectedDeployment && selectedNamespace) {
      checkForExistingSchedule();
    } else {
      setExistingScheduleForDeployment(null);
    }
  }, [selectedDeployment, selectedNamespace, isEditMode]);

  const loadNamespaces = async () => {
    try {
      const data = await k8sAPI.getNamespaces();
      // Backend now only returns allowed namespaces (with h8ber-mate label)
      setNamespaces(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load namespaces');
    }
  };

  const loadDeployments = async () => {
    try {
      setLoadingDeployments(true);
      const data = await k8sAPI.getDeployments(selectedNamespace);
      setDeployments(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load deployments');
    } finally {
      setLoadingDeployments(false);
    }
  };

  const checkForExistingSchedule = async () => {
    try {
      const allSchedules = await schedulesAPI.getAll();

      // Find if there's already a schedule for this namespace/deployment
      const existingSchedule = allSchedules.find(
        (s) =>
          s.namespace === selectedNamespace &&
          s.deployment_name === selectedDeployment
      );

      setExistingScheduleForDeployment(existingSchedule || null);
    } catch (err: any) {
      // Silently fail - this is just a warning check
      console.error('Failed to check for existing schedule:', err);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!selectedDeployment) {
      setError('Please select a deployment');
      return;
    }

    if (!isEditMode && existingScheduleForDeployment) {
      setError('A schedule already exists for this deployment. Please edit the existing schedule instead.');
      return;
    }

    try {
      setLoading(true);

      if (isEditMode && existingSchedule) {
        // Update existing schedule
        await schedulesAPI.update(existingSchedule.id, {
          scale_down_time: scaleDownTime,
          scale_up_time: scaleUpTime,
          enabled,
        });
      } else {
        // Create new schedule
        await schedulesAPI.create({
          namespace: selectedNamespace,
          deployment_name: selectedDeployment,
          scale_down_time: scaleDownTime,
          scale_up_time: scaleUpTime,
        });
      }

      onSuccess();
    } catch (err: any) {
      setError(err.response?.data?.detail || `Failed to ${isEditMode ? 'update' : 'create'} schedule`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {existingScheduleForDeployment && !isEditMode && (
        <div className="bg-yellow-50 border border-yellow-200 px-3 sm:px-4 py-3 rounded-lg">
          <div className="flex items-start gap-2 sm:gap-3">
            <svg className="w-5 h-5 text-yellow-600 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <div className="flex-1 min-w-0">
              <h4 className="text-xs sm:text-sm font-medium text-yellow-800 mb-1">
                Un schedule existe déjà pour ce déploiement
              </h4>
              <p className="text-xs sm:text-sm text-yellow-700 mb-2 break-words">
                Le déploiement <span className="font-semibold">{existingScheduleForDeployment.deployment_name}</span> dans le namespace{' '}
                <span className="font-semibold">{existingScheduleForDeployment.namespace}</span> a déjà un schedule configuré:
              </p>
              <div className="text-xs sm:text-sm text-yellow-700 space-y-1 ml-2 sm:ml-4">
                <div>• Scale Down: <span className="font-medium">{existingScheduleForDeployment.scale_down_time}</span></div>
                <div>• Scale Up: <span className="font-medium">{existingScheduleForDeployment.scale_up_time}</span></div>
                <div>• Status: {existingScheduleForDeployment.enabled ? (
                  <span className="font-medium text-green-700">Activé</span>
                ) : (
                  <span className="font-medium text-gray-600">Désactivé</span>
                )}</div>
              </div>
              <p className="text-xs sm:text-sm text-yellow-700 mt-2">
                Vous devez éditer le schedule existant au lieu d'en créer un nouveau.
              </p>
            </div>
          </div>
        </div>
      )}

      <div>
        <label htmlFor="namespace" className="block text-sm font-medium text-gray-700">
          Namespace
        </label>
        {isEditMode ? (
          <div className="mt-1 px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-700">
            {selectedNamespace}
          </div>
        ) : (
          <select
            id="namespace"
            value={selectedNamespace}
            onChange={(e) => setSelectedNamespace(e.target.value)}
            required
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          >
            <option value="">Select a namespace</option>
            {namespaces.map((ns) => (
              <option key={ns} value={ns}>
                {ns}
              </option>
            ))}
          </select>
        )}
      </div>

      <div>
        <label htmlFor="deployment" className="block text-sm font-medium text-gray-700">
          Deployment
        </label>
        {isEditMode ? (
          <div className="mt-1 px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-700">
            {selectedDeployment}
          </div>
        ) : (
          <select
            id="deployment"
            value={selectedDeployment}
            onChange={(e) => setSelectedDeployment(e.target.value)}
            required
            disabled={!selectedNamespace || loadingDeployments}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
          >
            <option value="">
              {loadingDeployments ? 'Loading...' : 'Select a deployment'}
            </option>
            {deployments.map((dep) => (
              <option key={dep.name} value={dep.name}>
                {dep.name} (Replicas: {dep.replicas})
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Preset Buttons */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">
          Quick Presets
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => {
              setScaleDownTime('19:00');
              setScaleUpTime('08:00');
            }}
            className="inline-flex items-center justify-center gap-2 px-3 sm:px-4 py-2 border border-indigo-300 text-xs sm:text-sm font-semibold rounded-lg text-indigo-700 bg-indigo-50 hover:bg-indigo-100 hover:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-all duration-200 hover:scale-105"
          >
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
            <span className="whitespace-nowrap">Night (19:00 → 08:00)</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setScaleDownTime('13:00');
              setScaleUpTime('14:00');
            }}
            className="inline-flex items-center justify-center gap-2 px-3 sm:px-4 py-2 border border-amber-300 text-xs sm:text-sm font-semibold rounded-lg text-amber-700 bg-amber-50 hover:bg-amber-100 hover:border-amber-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-amber-500 transition-all duration-200 hover:scale-105"
          >
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            <span className="whitespace-nowrap">Lunch (13:00 → 14:00)</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setScaleDownTime('18:00');
              setScaleUpTime('09:00');
            }}
            className="inline-flex items-center justify-center gap-2 px-3 sm:px-4 py-2 border border-purple-300 text-xs sm:text-sm font-semibold rounded-lg text-purple-700 bg-purple-50 hover:bg-purple-100 hover:border-purple-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 transition-all duration-200 hover:scale-105"
          >
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            <span className="whitespace-nowrap">Evening (18:00 → 09:00)</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setScaleDownTime('22:00');
              setScaleUpTime('08:00');
            }}
            className="inline-flex items-center justify-center gap-2 px-3 sm:px-4 py-2 border border-blue-300 text-xs sm:text-sm font-semibold rounded-lg text-blue-700 bg-blue-50 hover:bg-blue-100 hover:border-blue-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all duration-200 hover:scale-105"
          >
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <span className="whitespace-nowrap">Late Night (22:00 → 08:00)</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="scaleDownTime" className="block text-sm font-medium text-gray-700">
            Scale Down Time
          </label>
          <input
            type="time"
            id="scaleDownTime"
            value={scaleDownTime}
            onChange={(e) => setScaleDownTime(e.target.value)}
            required
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>

        <div>
          <label htmlFor="scaleUpTime" className="block text-sm font-medium text-gray-700">
            Scale Up Time
          </label>
          <input
            type="time"
            id="scaleUpTime"
            value={scaleUpTime}
            onChange={(e) => setScaleUpTime(e.target.value)}
            required
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>
      </div>

      <div className="flex items-center">
        <input
          type="checkbox"
          id="enabled"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
          className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
        />
        <label htmlFor="enabled" className="ml-2 block text-sm text-gray-700">
          Enable schedule immediately
        </label>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 pt-4">
        <button
          type="submit"
          disabled={loading || (!isEditMode && !!existingScheduleForDeployment)}
          className="flex-1 inline-flex justify-center items-center px-4 py-2.5 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (isEditMode ? 'Updating...' : 'Creating...') : (isEditMode ? 'Update Schedule' : 'Create Schedule')}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={loading}
          className="flex-1 inline-flex justify-center items-center px-4 py-2.5 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
};
