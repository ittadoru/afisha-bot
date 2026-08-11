"""Add category presentation, community scope, media variants and user cases."""
# ruff: noqa: E501

from collections.abc import Sequence

from alembic import op

revision: str = "0033_product_ui_data_foundation"
down_revision: str | None = "0032_notification_delivery_and_deduplication"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE discovery.categories
          ADD COLUMN icon_key varchar(40),
          ADD COLUMN color_key varchar(40);

        UPDATE discovery.categories SET icon_key = values.icon_key,
          color_key = values.color_key
        FROM (VALUES
          ('sport','dumbbell','emerald'), ('games','gamepad','violet'),
          ('meetups','users','blue'), ('cafe','coffee','amber'),
          ('tourism','mountain','teal'),
          ('education','graduation-cap','indigo'),
          ('creativity','palette','rose'), ('cars','car','slate-blue'),
          ('volunteering','hand-heart','cyan'),
          ('work','briefcase','brown'),
          ('entertainment','party-popper','orange'),
          ('walks','footprints','moss'), ('other','shapes','gray'),
          ('cinema','shapes','gray'), ('music','shapes','gray'),
          ('special','shapes','gray')
        ) AS values(slug, icon_key, color_key)
        WHERE discovery.categories.slug = values.slug;

        ALTER TABLE discovery.categories ALTER COLUMN icon_key SET NOT NULL;
        ALTER TABLE discovery.categories ALTER COLUMN color_key SET NOT NULL;

        UPDATE events.events SET category_id = (
          SELECT id FROM discovery.categories WHERE slug='other'
        ) WHERE category_id IN (
          SELECT id FROM discovery.categories
          WHERE slug IN ('cinema','music','special')
        );
        UPDATE discovery.looking_posts SET category_id = (
          SELECT id FROM discovery.categories WHERE slug='other'
        ) WHERE category_id IN (
          SELECT id FROM discovery.categories
          WHERE slug IN ('cinema','music','special')
        );
        UPDATE discovery.categories SET is_active=false
        WHERE slug IN ('cinema','music','special');

        ALTER TABLE events.events
          ADD COLUMN event_scope varchar(16) NOT NULL DEFAULT 'user';
        UPDATE events.events SET event_scope = CASE kind
          WHEN 'special' THEN 'community' ELSE 'user' END;
        ALTER TABLE events.events ADD CONSTRAINT ck_events_event_scope
          CHECK (event_scope IN ('user','community'));
        CREATE INDEX ix_events_scope_status
          ON events.events(event_scope,lifecycle_status);

        CREATE TABLE media.asset_variants (
          id uuid PRIMARY KEY,
          source_asset_id uuid NOT NULL REFERENCES media.assets(id) ON DELETE CASCADE,
          variant_key varchar(40) NOT NULL,
          storage_key text NOT NULL UNIQUE,
          mime_type varchar(100) NOT NULL,
          width integer NOT NULL CHECK (width > 0),
          height integer NOT NULL CHECK (height > 0),
          byte_size bigint NOT NULL CHECK (byte_size > 0),
          checksum_sha256 varchar(64) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE(source_asset_id,variant_key)
        );

        INSERT INTO media.asset_variants
          (id,source_asset_id,variant_key,storage_key,mime_type,width,height,
           byte_size,checksum_sha256)
        SELECT gen_random_uuid(),id,'avatar_256',storage_key,mime_type,width,height,
               byte_size,checksum_sha256
        FROM media.assets
        WHERE purpose='profile_avatar' AND state='ready'
          AND width=256 AND height=256
        ON CONFLICT (source_asset_id,variant_key) DO NOTHING;

        CREATE INDEX ix_messages_event_created_id
          ON communication.messages(event_id,created_at,id);

        CREATE TABLE trust_safety.moderation_cases (
          id uuid PRIMARY KEY,
          public_id varchar(11) NOT NULL UNIQUE,
          subject_type varchar(32) NOT NULL,
          subject_id uuid NOT NULL,
          subject_owner_user_id uuid,
          status varchar(16) NOT NULL DEFAULT 'received'
            CHECK (status IN ('received','reviewing','resolved')),
          priority varchar(16) NOT NULL DEFAULT 'normal'
            CHECK (priority IN ('normal','high','critical')),
          version integer NOT NULL DEFAULT 1 CHECK (version > 0),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          resolved_at timestamptz
        );
        CREATE INDEX ix_cases_owner_status_created
          ON trust_safety.moderation_cases(subject_owner_user_id,status,created_at DESC);

        CREATE TABLE trust_safety.reports (
          id uuid PRIMARY KEY,
          case_id uuid NOT NULL REFERENCES trust_safety.moderation_cases(id),
          reporter_user_id uuid NOT NULL,
          reason_code varchar(64) NOT NULL,
          explanation varchar(500),
          idempotency_key uuid NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE(reporter_user_id,idempotency_key)
        );
        CREATE INDEX ix_reports_reporter_created
          ON trust_safety.reports(reporter_user_id,created_at DESC);

        CREATE TABLE trust_safety.case_timeline_entries (
          id uuid PRIMARY KEY,
          case_id uuid NOT NULL REFERENCES trust_safety.moderation_cases(id),
          event_type varchar(32) NOT NULL,
          public_label varchar(160) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_case_timeline_case_created
          ON trust_safety.case_timeline_entries(case_id,created_at,id);

        CREATE TABLE trust_safety.appeals (
          id uuid PRIMARY KEY,
          case_id uuid NOT NULL REFERENCES trust_safety.moderation_cases(id),
          appellant_user_id uuid NOT NULL,
          explanation varchar(500) NOT NULL,
          status varchar(16) NOT NULL DEFAULT 'submitted'
            CHECK (status IN ('submitted','reviewing','upheld','reversed')),
          created_at timestamptz NOT NULL DEFAULT now(),
          decided_at timestamptz,
          UNIQUE(case_id,appellant_user_id)
        );

        INSERT INTO trust_safety.moderation_cases
          (id,public_id,subject_type,subject_id,subject_owner_user_id,status,
           priority,created_at,updated_at,resolved_at)
        SELECT id,
          'PV-' || upper(substr(replace(CAST(id AS text),'-',''),1,8)),
          'profile',subject_user_id,subject_user_id,
          CASE WHEN status IN ('pending','reviewed') THEN 'reviewing' ELSE 'resolved' END,
          'normal',created_at,COALESCE(decided_at,created_at),decided_at
        FROM trust_safety.profile_reports
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO trust_safety.reports
          (id,case_id,reporter_user_id,reason_code,explanation,idempotency_key,created_at)
        SELECT gen_random_uuid(),id,reporter_user_id,reason,comment,gen_random_uuid(),created_at
        FROM trust_safety.profile_reports
        WHERE EXISTS (SELECT 1 FROM trust_safety.moderation_cases c WHERE c.id=profile_reports.id);

        INSERT INTO trust_safety.case_timeline_entries
          (id,case_id,event_type,public_label,created_at)
        SELECT gen_random_uuid(),id,'received','Обращение получено',created_at
        FROM trust_safety.profile_reports;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE trust_safety.appeals;
        DROP TABLE trust_safety.case_timeline_entries;
        DROP TABLE trust_safety.reports;
        DROP TABLE trust_safety.moderation_cases;
        DROP INDEX communication.ix_messages_event_created_id;
        DROP TABLE media.asset_variants;
        DROP INDEX events.ix_events_scope_status;
        ALTER TABLE events.events DROP CONSTRAINT ck_events_event_scope;
        ALTER TABLE events.events DROP COLUMN event_scope;
        UPDATE discovery.categories SET is_active=true
          WHERE slug IN ('cinema','music','special');
        ALTER TABLE discovery.categories DROP COLUMN color_key;
        ALTER TABLE discovery.categories DROP COLUMN icon_key;
        """
    )
