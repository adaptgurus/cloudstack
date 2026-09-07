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

package preflight

import (
	"context"
	"errors"
	"reflect"
	"testing"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
)

type ancestryRunner struct {
	result executor.Result
	err    error
	path   string
	args   []string
	calls  int
}

func (r *ancestryRunner) Run(_ context.Context, path string, args ...string) (executor.Result, error) {
	r.calls++
	r.path = path
	r.args = append([]string{}, args...)
	return r.result, r.err
}

func TestAncestryUsesFullReverseLsblkChain(t *testing.T) {
	r := &ancestryRunner{result: executor.Result{Stdout: "/dev/null\n/dev/zero\n/dev/full\n"}}
	got, err := ancestry(context.Background(), r, "/dev/null")
	if err != nil {
		t.Fatalf("ancestry returned error: %v", err)
	}
	if r.calls != 1 {
		t.Fatalf("expected one lsblk call, got %d", r.calls)
	}
	if r.path != "/usr/bin/lsblk" {
		t.Fatalf("unexpected executable: %s", r.path)
	}
	wantArgs := []string{"-s", "-nrpo", "PATH", "/dev/null"}
	if !reflect.DeepEqual(r.args, wantArgs) {
		t.Fatalf("unexpected lsblk args: got=%v want=%v", r.args, wantArgs)
	}
	for _, path := range []string{"/dev/null", "/dev/zero", "/dev/full"} {
		if !got[path] {
			t.Fatalf("full reverse ancestry omitted %s: %#v", path, got)
		}
	}
}

func TestAncestryFailsClosedOnLsblkError(t *testing.T) {
	r := &ancestryRunner{err: errors.New("lsblk failed")}
	if _, err := ancestry(context.Background(), r, "/dev/null"); err == nil {
		t.Fatal("expected lsblk ancestry failure to fail closed")
	}
}

func TestAncestryRejectsEmptyOutput(t *testing.T) {
	r := &ancestryRunner{result: executor.Result{Stdout: "\n"}}
	if _, err := ancestry(context.Background(), r, "/dev/null"); err == nil {
		t.Fatal("expected empty ancestry to fail closed")
	}
}
