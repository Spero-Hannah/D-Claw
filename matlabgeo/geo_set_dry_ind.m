% geo_set_dry_ind sets dry_ind = NaN in cells where the
% depth is below cutoff and to 1 elsewhere.

cutoff= .99e-3;
dry_ind=ones(size(X));
dry_ind(find((h2./cutoff)<1))=NaN;
