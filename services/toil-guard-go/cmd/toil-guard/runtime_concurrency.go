package main

import (
	"context"
	"sync"
	"sync/atomic"
)

const (
	fixtureWorkers = 2
	fixtureJobs    = 6
)

type concurrencyMeasurements struct {
	Workers              int `json:"worker_limit"`
	Jobs                 int `json:"jobs"`
	PeakInFlight         int `json:"peak_in_flight"`
	Completed            int `json:"completed"`
	CancelPeakInFlight   int `json:"cancel_peak_in_flight"`
	CanceledInFlight     int `json:"canceled_in_flight"`
	NotStarted           int `json:"not_started_after_cancel"`
	CompletedAfterCancel int `json:"completed_after_cancel"`
}

func (m concurrencyMeasurements) passed() bool {
	return m.Workers == fixtureWorkers && m.Jobs == fixtureJobs && m.PeakInFlight == m.Workers &&
		m.Completed == m.Jobs && m.CancelPeakInFlight == m.Workers && m.CanceledInFlight == m.Workers &&
		m.NotStarted == m.Jobs-m.Workers && m.CompletedAfterCancel == 0
}

func measureLookupConcurrency() concurrencyMeasurements {
	normal := runConcurrencyFixture(false)
	canceled := runConcurrencyFixture(true)
	return concurrencyMeasurements{
		Workers: fixtureWorkers, Jobs: fixtureJobs, PeakInFlight: normal.peak,
		Completed: normal.completed, CancelPeakInFlight: canceled.peak,
		CanceledInFlight: canceled.canceled, NotStarted: fixtureJobs - canceled.started,
		CompletedAfterCancel: canceled.completed,
	}
}

type concurrencyState struct {
	started   atomic.Int32
	inFlight  atomic.Int32
	peak      atomic.Int32
	completed atomic.Int32
	canceled  atomic.Int32
}

type concurrencyResult struct {
	started   int
	peak      int
	completed int
	canceled  int
}

func runConcurrencyFixture(cancelDuringFirstBatch bool) concurrencyResult {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Two armed lookups stay in flight until the controller observes overlap.
	started := make(chan struct{}, fixtureJobs)
	release := make(chan struct{})
	jobs := make(chan int, fixtureJobs)
	for key := range fixtureJobs {
		jobs <- key
	}
	close(jobs)
	var state concurrencyState
	var workers sync.WaitGroup
	for range fixtureWorkers {
		workers.Go(func() { runFixtureWorker(ctx, &state, jobs, started, release) })
	}
	for range fixtureWorkers {
		<-started
	}
	if cancelDuringFirstBatch {
		cancel()
	} else {
		close(release)
	}
	workers.Wait()
	return concurrencyResult{
		started: int(state.started.Load()), peak: int(state.peak.Load()),
		completed: int(state.completed.Load()), canceled: int(state.canceled.Load()),
	}
}

func runFixtureWorker(ctx context.Context, state *concurrencyState, jobs <-chan int, started chan<- struct{}, release <-chan struct{}) {
	local := lookupFixture{values: [len(lookupKeys)]int{10, 20, 30, 40, 50, 60, 70, 80}}
	var answer [1]int
	for key := range jobs {
		if ctx.Err() != nil {
			return
		}
		state.started.Add(1)
		active := state.inFlight.Add(1)
		for highest := state.peak.Load(); active > highest; highest = state.peak.Load() {
			if state.peak.CompareAndSwap(highest, active) {
				break
			}
		}
		started <- struct{}{}
		select {
		case <-ctx.Done():
			state.canceled.Add(1)
		case <-release:
			if err := local.get(lookupKeys[key:key+1], answer[:]); err == nil && answer[0] == local.values[key] {
				state.completed.Add(1)
			}
		}
		state.inFlight.Add(-1)
	}
}
