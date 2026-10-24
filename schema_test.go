// SPDX-License-Identifier: Apache-2.0
package ostf_test

import (
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"testing"

	"github.com/google/jsonschema-go/jsonschema"
)

func TestSchemaFixtures(t *testing.T) {
	data, err := os.ReadFile("conformance/schema-cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []struct {
		ID, Schema string
		Input      any
		Valid      bool
	}
	if err := json.Unmarshal(data, &cases); err != nil {
		t.Fatal(err)
	}
	load := func(uri *url.URL) (*jsonschema.Schema, error) {
		if uri.Scheme != "https" || uri.Host != "ostf.dev" || filepath.Dir(uri.Path) != "/draft/0.2" {
			return nil, fmt.Errorf("schema reference is outside the local draft: %s", uri)
		}
		data, err := os.ReadFile(filepath.Join("schema", filepath.Base(uri.Path)))
		if err != nil {
			return nil, err
		}
		var schema jsonschema.Schema
		if err := json.Unmarshal(data, &schema); err != nil {
			return nil, err
		}
		return &schema, nil
	}
	for _, c := range cases {
		t.Run(c.ID, func(t *testing.T) {
			uri, err := url.Parse("https://ostf.dev/draft/0.2/" + c.Schema)
			if err != nil {
				t.Fatal(err)
			}
			schema, err := load(uri)
			if err != nil {
				t.Fatal(err)
			}
			resolved, err := schema.Resolve(&jsonschema.ResolveOptions{Loader: load})
			if err != nil {
				t.Fatal(err)
			}
			if err := resolved.Validate(c.Input); (err == nil) != c.Valid {
				t.Fatalf("valid %v; want %v: %v", err == nil, c.Valid, err)
			}
		})
	}
}
