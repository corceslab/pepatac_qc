#!/usr/bin/env python
# bamQC.py
#
# Last updated 7/11/18: Jason Smith
#
# Function: Script takes as input a BAM file and calculates the non-redundant
#           fraction (NRF) and the PCR bottleneck coefficients 1 (PBC1)
#           and 2 (PBC2). 
#

from argparse import ArgumentParser
import os
import sys

import pararead
from pararead.processor import _LOGGER

import pandas as _pd
import numpy as np

class bamQC(pararead.ParaReadProcessor):
    def __init__(self, reads_filename, n_proc, out_filename):
        """
        Derive from ParaReadProcessor to build the bamQC caller instance.

        Parameters
        ----------
        reads_filename : str
            Path to BAM file with aligned sequencing reads.
        n_proc : int, default 20
            Number of cores to use for processing.
        out_filename : str
            Name of output bamQC file
        """
        self.reads_filename = reads_filename
        super(bamQC, self).__init__(reads_filename, n_proc, out_filename)

    def register_files(self):
        """
        This function will make sure that the files needed for
        processing are stored in the module-level (global-like)
        variables stored in the pararead module, such that each child
        process can extract the assigned subset from the global files.
        """
        super(bamQC, self).register_files()

    def __call__(self, chrom):
        """
        Primary function of the method.
        This function takes a chrom, and processes the reads in that chromosome
        from the input bamfile

        @param chrom: a string with a chromosome, used by pysam.fetch to
        grab a subset of reads from the bamfile
        """

        chrom_size = self.get_chrom_size(chrom)
        
        ##### DEFINE FUNCTIONS #####
        def isPaired(chr):
            for read in chr:
                if read.is_paired:
                    return True
            return False

        def countFlags(chr):
            dups = 0
            unmap = 0
            unmap_mate = 0
            prop_pair = 0
            qcfail = 0
            num_pairs = 0
            for read in chr:
                if read.is_paired:
                    num_pairs += 1
                if read.is_duplicate:
                    dups += 1
                if read.is_unmapped:
                    unmap += 1
                if read.mate_is_unmapped:
                    unmap_mate += 1
                if read.is_proper_pair:
                    prop_pair += 1
                if read.is_qcfail:
                    qcfail += 1   
            return {'num_pairs':num_pairs/2, 'dups':dups, 'unmap':unmap,
                    'unmap_mate':unmap_mate, 'prop_pair':prop_pair,
                    'qcfail':qcfail}
            
        def getRead1(chr):
            keyDict = {'query_name', 'query_pos', 'template_length'}
            read1 = dict([(key, []) for key in keyDict])
            for read in chr:
                if read.is_paired:
                    if read.is_read1:
                        read1['query_name'].append(read.query_name)
                        read1['query_pos'].append(read.pos)
                        read1['template_length'].append(read.template_length)
            return _pd.DataFrame(read1)
        
        def getRead2(chr):
            keyDict = {'query_name', 'query_pos', 'template_length'}
            read2 = dict([(key, []) for key in keyDict])
            for read in chr:
                if read.is_paired:
                    if read.is_read2:
                        read2['query_name'].append(read.query_name)
                        read2['query_pos'].append(read.pos)
                        read2['template_length'].append(read.template_length)
            return _pd.DataFrame(read2)

        ##### MAIN #####
        _LOGGER.info("[Name: " + chrom + "; Size: " + str(chrom_size) + "]")
        if os.path.isfile(self.reads_filename):
            chrom_out_file = self._tempf(chrom)
            readCount = []
            chrStats = {}
            mitoCount = 0
            isPE = isPaired(self.fetch_chunk(chrom))   
            flags = countFlags(self.fetch_chunk(chrom))
            if isPE:
                read1 = getRead1(self.fetch_chunk(chrom))
                read2 = getRead2(self.fetch_chunk(chrom))
            merge = _pd.merge(read1, read2, on = 'query_name')
            merge = merge.drop(columns='query_name')
            if chrom == 'chrM':
                mitoCount = mitoCount + float(flags['num_pairs'])
            M_DISTINCT = len(merge.drop_duplicates())
            M1 = (flags['num_pairs']) - len(merge[merge.duplicated(keep=False)])
            posDup = merge[merge.duplicated(keep=False)]
            posDupTable = posDup.groupby(['query_pos_x','template_length_x']).count()
            cTable = posDupTable.groupby(['query_pos_y']).count()
            M2 = 0
            for key, value in cTable['template_length_y'].items():
                if key == 2:
                    M2 = value
            chrStats = {'M_DISTINCT':M_DISTINCT, 'M1':M1, 'M2':M2}         
            chrStats.update(flags)
            np.save(chrom_out_file, chrStats)
            return chrom
        else:
            _LOGGER.warn("{} could not be found.".format(self.reads_filename))
            return

    def combine(self, good_chromosomes, strict=False):
        """
        After running the process in parallel, this 'reduce' step will merge
        all the temporary files into one, calculate the NRF, PBC1, and PBC2
        and write those values to the outfile.
        """
        if not good_chromosomes:
            _LOGGER.warn("No successful chromosomes, so no combining.")
            return
        else:
            _LOGGER.info("Merging {} files into output file: '{}'".
                         format(len(good_chromosomes), self.outfile))
            temp_files = [self._tempf(chrom) for chrom in good_chromosomes]
            stats = {}
            for i in range(len(temp_files)):
                if not os.path.exists(temp_files[i] + '.npy'):
                    continue
                # load chrom data and add to dict                
                chrStats = np.load(temp_files[i] + '.npy')
                stats = {k: stats.get(k, 0) + chrStats.item().get(k, 0) for k in set(stats) | set(chrStats.item())}
            total = max(1, float(stats['num_pairs'])) 
            dupRate = stats['dups']/total
            NRF = float(stats['M1'])/total
            M2 = max(1, float(stats['M2']))
            PBC1 = float(stats['M1'])/max(1, float(stats['M_DISTINCT']))
            PBC2 = float(stats['M1'])/float(M2)
            header = ["Duplicate_rate", "NRF", "PBC1", "PBC2"]
            np.savetxt(self.outfile, np.c_[dupRate, NRF, PBC1, PBC2],
                       header='\t'.join(header), fmt='%s', delimiter='\t',
                       comments='')

# read options from command line
def parse_args(cmdl):
    parser = ArgumentParser(description='--Produce bamQC File--')
    parser.add_argument('-i', '--infile', dest='infile',
                        help="Path to input file (in BAM format).",
                        required=True)
    parser.add_argument('-o', '--outfile', dest='outfile',
                        help="Output file name.")
    parser.add_argument('-c', '--cores', dest='cores', default=20, type=int,
                        help="Number of processors to use. Default=20")
    return parser.parse_args(cmdl)
            
# parallel processed computation of matrix for each chromosome
if __name__ == "__main__":
    args = parse_args(sys.argv[1:])

    qc = bamQC(reads_filename=args.infile,
               out_filename=args.outfile,
               n_proc=args.cores)

    qc.register_files()
    good_chromosomes = qc.run()

    print("Reduce step (merge files)...")
    qc.combine(good_chromosomes)
