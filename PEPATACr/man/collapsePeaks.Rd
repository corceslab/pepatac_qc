% Generated by roxygen2: do not edit by hand
% Please edit documentation in R/PEPATACr.R
\name{collapsePeaks}
\alias{collapsePeaks}
\title{Internal helper function for \code{consensusPeaks}
Take a set of peak files and identify only the reproducible minimally
scoring peaks.}
\usage{
collapsePeaks(sample_table, chrom_sizes, min_score = 5)
}
\arguments{
\item{sample_table}{A data.table object that includes paths to
valid peak files.}

\item{chrom_sizes}{A data.table of genome chromosome sizes.}

\item{min_score}{A minimum peak score to keep.}
}
\description{
Internal helper function for \code{consensusPeaks}
Take a set of peak files and identify only the reproducible minimally
scoring peaks.
}
